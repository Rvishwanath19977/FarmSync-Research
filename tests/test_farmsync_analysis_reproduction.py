from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]

SCRIPT = (
    ROOT
    / "scripts"
    / "analyze_farmsync_final30.py"
)

REPRO_ROOT = (
    ROOT
    / "results"
    / "farmsync"
    / "reproduction"
)

SEALED_ANALYSIS = (
    ROOT
    / "results"
    / "farmsync"
    / "final30_analysis_v1"
)


def run_script(*args):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            *map(str, args),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_sealed_inputs_verify_cleanly():
    result = run_script(
        "--check-inputs"
    )

    assert result.returncode == 0, (
        result.stdout + result.stderr
    )

    assert (
        "Protected input verification: PASS"
        in result.stdout
    )

    assert (
        "Output path safety: PASS"
        in result.stdout
    )


def test_protected_analysis_output_is_rejected():
    result = run_script(
        "--seed-level",
        "--output-dir",
        SEALED_ANALYSIS,
    )

    combined = (
        result.stdout
        + result.stderr
    )

    assert result.returncode != 0

    assert (
        "Refusing to write inside sealed/protected path"
        in combined
    )


def test_seed_level_reproduction_matches_reference():
    output = (
        REPRO_ROOT
        / "pytest-seed-level"
    )

    if output.exists():
        shutil.rmtree(output)

    try:
        result = run_script(
            "--seed-level",
            "--output-dir",
            output,
        )

        assert result.returncode == 0, (
            result.stdout
            + result.stderr
        )

        assert (
            "Seed-level CSVs matching frozen reference: 7/7"
            in result.stdout
        )

        assert (
            "SEED-LEVEL REPRODUCTION: PASS"
            in result.stdout
        )

        stats = output / "statistics"

        expected = {
            "primary_seed_level.csv",
            "epsilon_seed_level.csv",
            "lambda_seed_level.csv",
            "alpha_seed_level.csv",
            "action_robustness_seed_level.csv",
            "uncertainty_seed_level.csv",
            "scalability_seed_level.csv",
        }

        assert {
            p.name
            for p in stats.glob("*.csv")
        } == expected

    finally:
        if output.exists():
            shutil.rmtree(output)

        if (
            REPRO_ROOT.exists()
            and not any(REPRO_ROOT.iterdir())
        ):
            REPRO_ROOT.rmdir()
