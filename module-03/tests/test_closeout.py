"""Read-only Story 10 checks for source accounting and verifiable evidence links."""

import ast
import hashlib
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "module-03/docs"
BASELINE = "8fc287d02a63ebac0218fde99cb36d21fe7d495b"
ARCHITECTURE_BLOB = "e23762cb5286470d3994aa98365a993d2b13248f"
EXPECTED_IDS = {
    f"M3-{category}-{number:02d}"
    for category, count in (
        ("RAG", 4),
        ("RET", 4),
        ("VS", 3),
        ("CTX", 5),
        ("LAB", 4),
        ("TOOL", 5),
        ("DEL", 2),
        ("PORT", 1),
    )
    for number in range(1, count + 1)
}


def _rows(path: Path) -> dict[str, list[str]]:
    """Read requirement rows while rejecting duplicate IDs."""
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\| M3-[A-Z]+-\d{2} \|", line):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            assert cells[0] not in rows, "Duplicate requirement row"
            rows[cells[0]] = cells
    return rows


def _baseline(path: str) -> str:
    """Read the accepted Git blob without changing index or history."""
    result = subprocess.run(
        ["git", "show", f"{BASELINE}:{path}"],
        cwd=ROOT,
        capture_output=True,
        check=True,
        timeout=30,
    )
    return result.stdout.decode("utf-8").replace("\r\n", "\n")


def test_source_accounting_and_supported_status_changes() -> None:
    """Account for the exact frozen IDs without changing authoritative wording."""
    source = DOCS / "SOURCE_REQUIREMENTS.md"
    rows = _rows(source)
    assert set(rows) == EXPECTED_IDS
    assert len(rows) == 28
    assert all(row[-1] == "Complete" for row in rows.values())
    current = source.read_text(encoding="utf-8")
    assert "- [ ]" not in current
    restored = current.replace("| Complete |", "| Pending |").replace("- [x]", "- [ ]")
    assert restored == _baseline("module-03/docs/SOURCE_REQUIREMENTS.md")


def test_traceability_is_complete_and_unique() -> None:
    """Require one evidence-bearing row per source ID, with no stray ID claims."""
    trace = DOCS / "TRACEABILITY.md"
    rows = _rows(trace)
    assert set(rows) == EXPECTED_IDS
    identities = re.findall(r"M3-[A-Z]+-\d{2}", trace.read_text(encoding="utf-8"))
    assert len(identities) == len(set(identities)) == 28
    for row in rows.values():
        assert len(row) == 7
        assert all(row)
        assert "](../src/" in row[2] or "](../app.py)" in row[2]
        assert "](../tests/" in row[3]
        assert row[5].startswith("Complete")


def test_closeout_links_and_named_test_evidence_resolve() -> None:
    """Catch stale file/test references instead of checking decorative text alone."""
    files = [
        DOCS / name for name in ("TRACEABILITY.md", "VERIFICATION.md", "STORY_10.md")
    ]
    files.append(ROOT / "README.md")
    for document in files:
        assert document.is_file()
        for label, target in re.findall(
            r"\[([^\]]+)\]\(([^)]+)\)", document.read_text(encoding="utf-8")
        ):
            if target.startswith(("https://", "http://", "#")):
                continue
            path = (document.parent / target.split("#", 1)[0]).resolve()
            assert path.is_relative_to(ROOT)
            assert path.is_file(), f"Missing referenced file: {target}"
            if path.suffix == ".py" and re.fullmatch(r"test_\w+", label):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                names = {
                    node.name for node in tree.body if isinstance(node, ast.FunctionDef)
                }
                assert label in names, f"Missing named test: {label}"


def test_integration_claims_preserve_verification_qualifications() -> None:
    """Offline providers cannot silently become live-verification claims."""
    rows = _rows(DOCS / "TRACEABILITY.md")
    for identity in ("M3-VS-03", "M3-TOOL-03"):
        assert "offline verification" in rows[identity][5]
        assert "no live remote-service verification" in rows[identity][6].casefold()
    assert "offline verification" in rows["M3-TOOL-05"][5]
    assert "no live api verification" in rows["M3-TOOL-05"][6].casefold()
    for identity in ("M3-TOOL-01", "M3-TOOL-02", "M3-TOOL-04"):
        assert "genuine local runtime" in rows[identity][5]
    assert "supplied human review" in rows["M3-PORT-01"][5]
    verification = (DOCS / "VERIFICATION.md").read_text(encoding="utf-8")
    assert "This agent did not conduct a new manual browser review" in " ".join(
        verification.split()
    )


def test_frozen_architecture_and_module_roadmap() -> None:
    """Keep the accepted architecture blob and separate engineering/release state."""
    architecture = (DOCS / "ARCHITECTURE.md").read_text(encoding="utf-8").encode()
    header = f"blob {len(architecture)}\0".encode()
    assert hashlib.sha1(header + architecture).hexdigest() == ARCHITECTURE_BLOB
    assert architecture.decode() == _baseline("module-03/docs/ARCHITECTURE.md")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert (
        "| Module 3 - RAG Engineering Foundations | Complete / release-ready |"
        in readme
    )
    assert "| Modules 4-12 | Planned |" in readme
    assert "Modules 3-12 | Planned" not in readme
    assert "No Module 3 Git release/tag is claimed" in readme
    for heading in (
        "## Module 2 - Prompt Engineering & Structured Output Systems",
        "## Module 1 - Python, APIs, and LLM SDK Foundations",
    ):
        assert (
            readme.split(heading, 1)[1] == _baseline("README.md").split(heading, 1)[1]
        )
