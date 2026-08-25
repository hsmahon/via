"""The agent runner: Via's minimal, explicit execution loop.

Responsibilities implemented here (and nowhere else):

1. Agent invocation            - :meth:`AgentRunner.execute`
2. Session/request identity    - :class:`RunContext` creation
3. Prompt resolution           - via ``PromptResolver`` port
4. Tool discovery              - via ``ToolRegistry`` port
5. Tool authorization          - via ``Authorizer`` port (denial aborts run)
6. Tool invocation             - via ``ToolExecutor`` (validation + timeout)
7. Context management          - conversation assembly for this run only
8. Error handling              - taxonomy in ``errors.py``, never swallowed
9. Timeouts                    - per-tool contract deadlines
10. Structured outputs         - strict JSON wire-contract validation
11. Tracing                    - spans for every phase
12. Metrics/cost telemetry     - counters plus usage aggregation

There is deliberately no multi-agent orchestration, no autonomous background
agents, no memory beyond the single-run conversation, no RAG and no
embeddings.
"""

from __future__ import annotations

import json
import time

from pydantic import BaseModel, Field

from via_harness.context import AuthorizationContext, RunContext, new_id
from via_harness.errors import ErrorCategory, HarnessError, RunFailure
from via_harness.model.base import ModelClient
from via_harness.model.types import (
    ModelMessage,
    ModelRequest,
    ModelRole,
    ModelToolSpec,
    TokenUsage,
)
from via_harness.policy import Authorizer, authorization_denied
from via_harness.prompts.base import Prompt, PromptResolver, render_prompt
from via_harness.response import (
    AgentResponse,
    FinalAnswer,
    ToolRequest,
    final_response_instruction,
    parse_model_output,
    validate_agent_answer,
)
from via_harness.tools.base import ToolContract
from via_harness.tools.executor import ToolExecutor
from via_harness.tools.registry import ToolRegistry
from via_harness.tracing import MetricsSink, SpanHandle, SpanRecord, Tracer, new_trace_id

__all__ = ["AgentRequest", "AgentRunResult", "AgentRunner", "StepSummary"]


class AgentRequest(BaseModel):
    """Input to one agent invocation."""

    message: str = Field(min_length=1, max_length=4000)
    video_id: str = Field(min_length=1)
    session_id: str | None = None
    prompt_name: str = Field(default="video_assistant")
    max_steps: int = Field(
        default=3, ge=1, le=6, description="Upper bound on model invocations for this run."
    )


class StepSummary(BaseModel):
    """Traceable summary of a single executed step."""

    step: int
    kind: str  # "model" | "tool"
    name: str
    status: str
    latency_ms: float
    detail: str | None = None


class AgentRunResult(BaseModel):
    """Complete outcome of an agent run, success or failure."""

    run_id: str
    trace_id: str
    session_id: str
    video_id: str
    agent_version: str
    status: str  # "completed" | "failed"
    response: AgentResponse | None = None
    failure: RunFailure | None = None
    steps: list[StepSummary] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    usage: TokenUsage = Field(default_factory=TokenUsage)

    @property
    def completed(self) -> bool:
        """Whether the run finished with a validated answer.

        Returns:
            True when ``status`` is ``completed``.
        """
        return self.status == "completed"


class AgentRunner:
    """Orchestrates one authorized agent interaction through the ports."""

    def __init__(
        self,
        *,
        model: ModelClient,
        prompts: PromptResolver,
        tools: ToolRegistry,
        authorizer: Authorizer,
        tracer: Tracer,
        metrics: MetricsSink | None = None,
        agent_version: str = "0.1.0",
        prompt_globals: dict[str, str] | None = None,
        max_tokens: int = 1024,
        model_timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize the runner with its collaborators.

        Args:
            model: Backend-agnostic model client.
            prompts: Prompt resolution port.
            tools: Tool discovery port.
            authorizer: Policy deciding tool permissions/access.
            tracer: Span recorder.
            metrics: Optional counter sink.
            agent_version: Version stamped onto runs and traces.
            prompt_globals: Template variables applied to every prompt
                render before request-specific ones.
            max_tokens: Generation budget forwarded to the model client.
            model_timeout_seconds: Wall-clock budget per model invocation.
        """
        self._model = model
        self._prompts = prompts
        self._tools = tools
        self._authorizer = authorizer
        self._tracer = tracer
        self._metrics = metrics
        self._agent_version = agent_version
        self._prompt_globals = prompt_globals or {}
        self._max_tokens = max_tokens
        self._model_timeout_seconds = model_timeout_seconds
        self._executor = ToolExecutor()

    def execute(self, request: AgentRequest, authz: AuthorizationContext) -> AgentRunResult:
        """Run the full loop: resolve, discover, invoke, validate, trace.

        Args:
            request: The user-facing invocation request.
            authz: Authorization context derived from authentication.

        Returns:
            Completed or failed run result. Expected harness errors are
            captured into ``failure``; truly unexpected exceptions are
            recorded on the trace and re-raised wrapped as
            ``INTERNAL_ERROR``.
        """
        run_id = new_id("run")
        trace_id = new_trace_id()
        session_id = request.session_id or new_id("sess")
        started = time.perf_counter()
        ctx = RunContext(
            run_id=run_id,
            trace_id=trace_id,
            session_id=session_id,
            user_id=authz.user_id,
            video_id=request.video_id,
            agent_version=self._agent_version,
        )
        root_record, root_span = self._start_root(ctx, request)
        steps: list[StepSummary] = []
        usage = TokenUsage()
        try:
            response = self._loop(request, authz, ctx, root_record.span_id, steps, usage)
            if self._metrics is not None:
                self._metrics.increment("agent.runs.completed")
            self._tracer.end_span(root_record)
            return AgentRunResult(
                run_id=ctx.run_id,
                trace_id=ctx.trace_id,
                session_id=ctx.session_id,
                video_id=ctx.video_id,
                agent_version=ctx.agent_version,
                status="completed",
                response=response,
                steps=steps,
                total_latency_ms=_elapsed_ms(started),
                usage=usage,
            )
        except HarnessError as error:
            error.run_id = error.run_id or run_id
            root_span.record_error(error.category, error.message)
            if self._metrics is not None:
                self._metrics.increment(
                    "agent.runs.failed", tags={"category": error.category.value}
                )
            self._tracer.end_span(root_record)
            return AgentRunResult(
                run_id=ctx.run_id,
                trace_id=ctx.trace_id,
                session_id=ctx.session_id,
                video_id=ctx.video_id,
                agent_version=ctx.agent_version,
                status="failed",
                failure=RunFailure.from_error(error),
                steps=steps,
                total_latency_ms=_elapsed_ms(started),
                usage=usage,
            )
        except Exception as error:
            root_span.record_error(ErrorCategory.INTERNAL_ERROR, str(error))
            if self._metrics is not None:
                self._metrics.increment(
                    "agent.runs.failed", tags={"category": ErrorCategory.INTERNAL_ERROR.value}
                )
            self._tracer.end_span(root_record)
            raise HarnessError(
                ErrorCategory.INTERNAL_ERROR,
                f"unexpected runner failure: {error}",
                run_id=run_id,
            ) from error

    # ------------------------------------------------------------------
    # Loop internals
    # ------------------------------------------------------------------

    def _start_root(self, ctx: RunContext, request: AgentRequest) -> tuple[SpanRecord, SpanHandle]:
        """Open the run's root span with identity attributes.

        Args:
            ctx: Run context.
            request: Original request for correlation fields.

        Returns:
            Root span record and handle.
        """
        record, handle = self._tracer.start_span(
            run_id=ctx.run_id,
            trace_id=ctx.trace_id,
            name="agent.run",
            user_id=ctx.user_id,
            video_id=request.video_id,
            agent_version=self._agent_version,
        )
        return record, handle

    def _loop(
        self,
        request: AgentRequest,
        authz: AuthorizationContext,
        ctx: RunContext,
        parent_span_id: str,
        steps: list[StepSummary],
        usage: TokenUsage,
    ) -> AgentResponse:
        """Execute prompt/tool/model rounds until a valid final answer.

        Args:
            request: Original invocation request.
            authz: Authorization context for this run.
            ctx: Run identity/correlation context.
            parent_span_id: Root span id for child spans.
            steps: Mutable list collecting step summaries.
            usage: Mutable token accumulator.

        Returns:
            Validated client-facing answer.

        Raises:
            HarnessError: On any categorized failure (authorization denial,
                invalid model output, exhausted steps, ...).
        """
        prompt = self._resolve_prompt(ctx, parent_span_id, request)

        available = self._tools.get_tools(authz)
        specs = [ModelToolSpec(**tool.contract.model_tool_spec()) for tool in available]
        variable_pool = {
            **self._prompt_globals,
            "video_id": request.video_id,
            "user_id": authz.user_id,
        }
        variables = {key: value for key, value in variable_pool.items() if key in prompt.variables}
        system = render_prompt(prompt, **variables) + "\n" + final_response_instruction()

        messages: list[ModelMessage] = [ModelMessage(role=ModelRole.USER, content=request.message)]
        for step in range(1, request.max_steps + 1):
            raw_text = self._invoke_model(
                ctx, parent_span_id, system, messages, specs, step, steps, usage
            )
            parsed = parse_model_output(raw_text)
            if isinstance(parsed, FinalAnswer):
                validate_record, _handle = self._tracer.start_span(
                    run_id=ctx.run_id,
                    trace_id=ctx.trace_id,
                    name="response.validate",
                    parent_span_id=parent_span_id,
                    step=step,
                )
                answer = validate_agent_answer(parsed, video_id=request.video_id)
                self._tracer.end_span(validate_record)
                return AgentResponse(answer=answer.answer, citations=list(answer.citations))

            tool_message = self._run_tool(ctx, parent_span_id, parsed, authz, step, steps)
            messages.append(
                ModelMessage(role=ModelRole.ASSISTANT, content=parsed.model_dump_json())
            )
            messages.append(tool_message)

        raise HarnessError(
            ErrorCategory.INVALID_MODEL_RESPONSE,
            f"Model failed to produce a final answer within {request.max_steps} steps",
            run_id=ctx.run_id,
            details={"max_steps": request.max_steps},
        )

    def _resolve_prompt(
        self, ctx: RunContext, parent_span_id: str, request: AgentRequest
    ) -> Prompt:
        """Resolve the run's system prompt inside a traced span.

        Args:
            ctx: Run context.
            parent_span_id: Parent span id.
            request: Request carrying the prompt name.

        Returns:
            The resolved immutable prompt.

        Raises:
            HarnessError: Propagates resolver failures unchanged.
        """
        record, handle = self._tracer.start_span(
            run_id=ctx.run_id,
            trace_id=ctx.trace_id,
            name="prompt.resolve",
            parent_span_id=parent_span_id,
            prompt_name=request.prompt_name,
        )
        try:
            prompt = self._prompts.get_prompt(request.prompt_name)
        except HarnessError as error:
            handle.record_error(error.category, error.message)
            self._tracer.end_span(record)
            raise
        handle.set_attribute("prompt.version", prompt.version)
        handle.set_attribute("prompt.environment", prompt.environment.value)
        self._tracer.end_span(record)
        return prompt

    def _invoke_model(
        self,
        ctx: RunContext,
        parent_span_id: str,
        system: str,
        messages: list[ModelMessage],
        specs: list[ModelToolSpec],
        step: int,
        steps: list[StepSummary],
        usage: TokenUsage,
    ) -> str:
        """Invoke the model inside a traced span and return raw text.

        Args:
            ctx: Run context.
            parent_span_id: Parent span id.
            system: Rendered system prompt.
            messages: Current conversation.
            specs: Discoverable tool specs.
            step: One-based step number.
            steps: Mutable step-summary sink.
            usage: Mutable token accumulator.

        Returns:
            Raw text produced by the model.

        Raises:
            HarnessError: Propagated ``MODEL_ERROR``/``TIMEOUT`` failures.
        """
        record, span = self._tracer.start_span(
            run_id=ctx.run_id,
            trace_id=ctx.trace_id,
            name="model.invoke",
            parent_span_id=parent_span_id,
            step=step,
        )
        started = time.perf_counter()
        try:
            response = self._model.invoke(
                ModelRequest(
                    messages=messages, system=system, tools=specs, max_tokens=self._max_tokens
                ),
                timeout_seconds=self._model_timeout_seconds,
            )
        except HarnessError as error:
            span.record_error(error.category, error.message)
            self._tracer.end_span(record)
            steps.append(
                StepSummary(
                    step=step,
                    kind="model",
                    name="model.invoke",
                    status="error",
                    latency_ms=_elapsed_ms(started),
                    detail=error.message,
                )
            )
            raise
        span.set_attribute("model.id", response.model_id or "")
        if response.usage:
            usage.input_tokens = (usage.input_tokens or 0) + (response.usage.input_tokens or 0)
            usage.output_tokens = (usage.output_tokens or 0) + (response.usage.output_tokens or 0)
        self._tracer.end_span(record)
        steps.append(
            StepSummary(
                step=step,
                kind="model",
                name=response.model_id or "model",
                status=str(response.stop_reason.value),
                latency_ms=_elapsed_ms(started),
            )
        )
        if self._metrics is not None:
            self._metrics.increment("agent.model.invocations")
        return response.text or ""

    def _run_tool(
        self,
        ctx: RunContext,
        parent_span_id: str,
        payload: ToolRequest,
        authz: AuthorizationContext,
        step: int,
        steps: list[StepSummary],
    ) -> ModelMessage:
        """Authorize and execute a model-requested tool call.

        Authorization denial aborts the whole run immediately - the model is
        never given feedback it could reason around. Unknown tools and tool
        failures are fed back as structured error results so the model can
        finalize gracefully within the step budget.

        Args:
            ctx: Run context.
            parent_span_id: Parent span id.
            payload: Parsed tool request from the model output.
            authz: Authorization context of the caller.
            step: One-based step number.
            steps: Mutable step-summary sink.

        Returns:
            The ``TOOL`` role message carrying the JSON-encoded result.

        Raises:
            HarnessError: ``AUTHORIZATION_ERROR`` when the policy denies the
                invocation; propagated tool timeouts are converted into
                error results instead.
        """
        tool = self._tools.get_tool(payload.tool)
        if tool is None:
            body: dict[str, object] = {
                "type": "tool_result",
                "tool": payload.tool,
                "status": "error",
                "detail": f"unknown tool '{payload.tool}'",
            }
            return ModelMessage(role=ModelRole.TOOL, content=json.dumps(body))

        contract: ToolContract = tool.contract
        decision = self._authorizer.authorize(contract, authz)
        if not decision.allowed:
            steps.append(
                StepSummary(
                    step=step,
                    kind="tool",
                    name=contract.name,
                    status="denied",
                    latency_ms=0.0,
                    detail=decision.reason,
                )
            )
            raise authorization_denied(decision.reason, run_id=ctx.run_id)

        record, span = self._tracer.start_span(
            run_id=ctx.run_id,
            trace_id=ctx.trace_id,
            name="tool.invoke",
            parent_span_id=parent_span_id,
            tool_name=contract.name,
            tool_version=contract.version,
            tool_owner=contract.owner,
            step=step,
        )
        started = time.perf_counter()
        try:
            result = self._executor.execute(
                tool,
                video_id=authz.video_id,
                authz=authz,
                arguments=payload.arguments,
                run_id=ctx.run_id,
            )
        except HarnessError as error:
            span.record_error(error.category, error.message)
            self._tracer.end_span(record)
            steps.append(
                StepSummary(
                    step=step,
                    kind="tool",
                    name=contract.name,
                    status="error",
                    latency_ms=_elapsed_ms(started),
                    detail=error.message,
                )
            )
            body = {
                "type": "tool_result",
                "tool": contract.name,
                "status": "error",
                "detail": error.message,
            }
            return ModelMessage(role=ModelRole.TOOL, content=json.dumps(body))

        body = {
            "type": "tool_result",
            "tool": contract.name,
            "status": result.status.value,
        }
        if result.payload is not None:
            body["payload"] = result.payload
        if result.detail:
            body["detail"] = result.detail
        span.set_attribute("tool.status", result.status.value)
        span.set_attribute("latency.ms", result.latency_ms)
        self._tracer.end_span(record)
        steps.append(
            StepSummary(
                step=step,
                kind="tool",
                name=contract.name,
                status=result.status.value,
                latency_ms=float(result.latency_ms),
            )
        )
        return ModelMessage(role=ModelRole.TOOL, content=json.dumps(body))


def _elapsed_ms(started: float) -> float:
    """Compute elapsed milliseconds since ``started``.

    Args:
        started: ``time.perf_counter`` stamp.

    Returns:
        Elapsed milliseconds rounded to three decimals.
    """
    return round((time.perf_counter() - started) * 1000, 3)
