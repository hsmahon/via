/**
 * Docstring (JSDoc) enforcement tests for the UI package.
 *
 * Mirrors the Python docstring meta-tests: every exported symbol in src/
 * must carry a JSDoc block. Uses the TypeScript compiler API for reliable
 * parsing rather than regex heuristics.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { basename, join } from "node:path";
import ts from "typescript";
import { describe, expect, it } from "vitest";

const SRC = join(__dirname, "..", "src");

/**
 * Collect all .ts/.tsx source files under a directory recursively.
 *
 * @param dir - Directory to scan.
 * @returns Absolute file paths.
 */
function collectFiles(dir: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      files.push(...collectFiles(full));
    } else if (
      (entry.endsWith(".ts") || entry.endsWith(".tsx")) &&
      !entry.endsWith(".d.ts")
    ) {
      files.push(full);
    }
  }
  return files;
}

/**
 * Check whether one source file has JSDoc on all exported symbols.
 *
 * @param file - Path of the file being scanned.
 * @returns Offense descriptions; empty when fully documented.
 */
function scanFile(file: string): string[] {
  const source = ts.createSourceFile(
    basename(file),
    readFileSync(file, "utf-8"),
    ts.ScriptTarget.Latest,
    true,
  );
  const offenses: string[] = [];

  source.forEachChild((node) => {
    const modifiers = ts.canHaveModifiers(node) ? ts.getModifiers(node) : undefined;
    const isExported =
      modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword) ?? false;
    if (!isExported) return;

    let name = "";
    if (ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node)) {
      name = node.name?.text ?? "<anonymous>";
    } else if (ts.isVariableStatement(node)) {
      name = node.declarationList.declarations
        .map((d) => (ts.isIdentifier(d.name) ? d.name.text : ""))
        .join(", ");
    } else if (
      ts.isInterfaceDeclaration(node) ||
      ts.isTypeAliasDeclaration(node) ||
      ts.isEnumDeclaration(node)
    ) {
      name = node.name.text;
    } else {
      return;
    }

    const hasJsDoc = ts.getJSDocCommentsAndTags(node).length > 0;
    if (!hasJsDoc) {
      offenses.push(`${basename(file)}: exported '${name}' is missing JSDoc`);
    }
  });

  return offenses;
}

describe("jsdoc coverage", () => {
  /** The scan must actually see sources to be meaningful. */
  it("scans at least one file", () => {
    expect(collectFiles(SRC).length).toBeGreaterThan(0);
  });

  /** Every exported symbol carries a JSDoc docstring. */
  it("documents every exported symbol", () => {
    const offenders = collectFiles(SRC).flatMap(scanFile);
    expect(offenders).toEqual([]);
  });
});
