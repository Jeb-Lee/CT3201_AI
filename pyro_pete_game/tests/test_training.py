"""Checks for the training tooling: run logs, the epoch-vs-accuracy report,
screen recording, and a tiny real training run.

The log/report tests need only numpy + (optionally) matplotlib. The training
run needs stable-baselines3 and skips cleanly without it. Run:
    python -m pytest     (from pyro_pete_game/)
"""

import importlib.util
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
import pytest

pygame.init()
pygame.display.set_mode((960, 640))

from ml import report                                      # noqa: E402
from ml.report import CsvLog, EPOCH_FIELDS, EVAL_FIELDS, read_csv  # noqa: E402

HAVE_MPL = importlib.util.find_spec("matplotlib") is not None
HAVE_SB3 = (importlib.util.find_spec("stable_baselines3") is not None
            and importlib.util.find_spec("gymnasium") is not None)
HAVE_FFMPEG = __import__("shutil").which("ffmpeg") is not None


# --------------------------------------------------------------- csv logging
def test_csvlog_writes_one_header_and_appends(tmp_path):
    path = str(tmp_path / "epochs.csv")
    log = CsvLog(path, ["epoch", "train_accuracy"])
    log.write({"epoch": 1, "train_accuracy": 0.25})
    log.close()
    log = CsvLog(path, ["epoch", "train_accuracy"])          # a resumed run
    log.write({"epoch": 2, "train_accuracy": 0.5})
    log.close()
    lines = open(path).read().strip().splitlines()
    assert lines[0] == "epoch,train_accuracy" and len(lines) == 3


def test_csvlog_rows_are_readable_while_the_file_is_still_open(tmp_path):
    path = str(tmp_path / "e.csv")
    log = CsvLog(path, ["epoch", "x"])
    log.write({"epoch": 1, "x": 3})
    assert read_csv(path) == [{"epoch": 1, "x": 3}]           # flushed, not buffered
    log.close()


def test_csvlog_blanks_none_and_nan_and_ignores_extra_keys(tmp_path):
    path = str(tmp_path / "e.csv")
    log = CsvLog(path, ["epoch", "a", "b"])
    log.write({"epoch": 1, "a": None, "b": float("nan"), "junk": 5})
    log.close()
    assert read_csv(path) == [{"epoch": 1, "a": None, "b": None}]


def test_read_csv_converts_numbers_and_handles_a_missing_file(tmp_path):
    assert read_csv(str(tmp_path / "nope.csv")) == []
    p = tmp_path / "t.csv"
    p.write_text("a,b,c\n1,2.5,word\n")
    assert read_csv(str(p)) == [{"a": 1, "b": 2.5, "c": "word"}]


def test_last_epoch(tmp_path):
    assert report.last_epoch(str(tmp_path)) == 0
    log = CsvLog(str(tmp_path / "epochs.csv"), EPOCH_FIELDS)
    for e in (1, 2, 3):
        log.write({"epoch": e})
    log.close()
    assert report.last_epoch(str(tmp_path)) == 3


# ------------------------------------------------------------ chart + report
def _synthetic_run(run_dir):
    ep = CsvLog(os.path.join(run_dir, "epochs.csv"), EPOCH_FIELDS)
    for e in range(1, 6):
        ep.write({"epoch": e, "timesteps": e * 1000, "window_episodes": 10 * e,
                  "train_accuracy": e / 10, "score": 20.0 * e, "policy_loss": -0.01,
                  "value_loss": 100.0 / e, "entropy": 1.0 - e / 10, "died": 0.5})
    ep.close()
    ev = CsvLog(os.path.join(run_dir, "evaluations.csv"), EVAL_FIELDS)
    base = dict(stages="1 2", episodes=10, died=0, gave_up=0, timeout=0, occupants_out=1,
                seconds=30, score_ci=5)
    for split in ("train", "heldout"):
        ev.write(dict(base, epoch=0, timesteps=0, agent="astar", split=split, accuracy=0.9,
                      accuracy_lo=0.6, accuracy_hi=0.98, score=400))
        for e in (0, 3, 5):
            ev.write(dict(base, epoch=e, timesteps=e * 1000, agent="model", split=split,
                          accuracy=e / 10, accuracy_lo=max(0, e / 10 - 0.2),
                          accuracy_hi=min(1, e / 10 + 0.2), score=40 * e))
    ev.close()


@pytest.mark.skipif(not HAVE_MPL, reason="matplotlib not installed")
def test_plot_run_draws_the_epoch_vs_accuracy_chart(tmp_path):
    _synthetic_run(str(tmp_path))
    path = report.plot_run(str(tmp_path))
    assert path and os.path.isfile(path) and os.path.getsize(path) > 5000
    assert os.path.basename(path) == "epoch_vs_accuracy.png"


def test_plot_run_with_nothing_logged_is_a_no_op(tmp_path):
    assert report.plot_run(str(tmp_path)) is None


def test_write_report_summarises_the_run(tmp_path):
    _synthetic_run(str(tmp_path))
    os.makedirs(tmp_path / "videos")
    (tmp_path / "videos" / "step_000001000_stage01.mp4").write_bytes(b"x")
    (tmp_path / "config.json").write_text('{"algo": "maskable"}')
    (tmp_path / "final_report.txt").write_text("best beat astar <maybe>")
    text = open(report.write_report(str(tmp_path), live=True), encoding="utf-8").read()
    assert "epoch <b>5</b>" in text
    assert "HELD-OUT" in text and "A* (baseline)" in text
    assert "step_000001000_stage01.mp4" in text
    assert "maskable" in text
    assert 'http-equiv="refresh"' in text                     # live page refreshes itself
    assert "&lt;maybe&gt;" in text                            # user text is escaped
    done = open(report.write_report(str(tmp_path), live=False), encoding="utf-8").read()
    assert 'http-equiv="refresh"' not in done


def test_write_report_on_an_empty_folder_does_not_crash(tmp_path):
    assert os.path.isfile(report.write_report(str(tmp_path)))


# ------------------------------------------------------------------ recording
def test_record_episode_writes_a_video(tmp_path):
    from ml.recording import record_episode
    out = record_episode("stay", 0, seed=1, path=str(tmp_path / "clip.mp4"),
                         max_seconds=4, speed=4, caption="test")
    assert os.path.isfile(out["video"]) and os.path.getsize(out["video"]) > 1000
    assert out["video"].endswith(".mp4" if HAVE_FFMPEG else ".gif")
    assert out["outcome"] in ("timeout", "gave_up")
    assert out["agent"] == "stay" and out["stage"] == 0


def test_recording_does_not_change_what_happens(tmp_path):
    """Watching is passive: a recorded episode ends exactly like an unrecorded one."""
    from ml import evaluation
    from ml.recording import record_episode
    plain = evaluation.run_episode("astar", 0, seed=5, max_seconds=60)
    filmed = record_episode("astar", 0, seed=5, path=str(tmp_path / "a.mp4"),
                            max_seconds=60, speed=8)
    for key in ("outcome", "victims_out", "score", "seconds"):
        assert plain[key] == filmed[key]


def test_gif_fallback_when_ffmpeg_is_missing(tmp_path, monkeypatch):
    from ml import recording
    monkeypatch.setattr(recording, "find_ffmpeg", lambda: None)
    out = recording.record_episode("stay", 0, seed=1, path=str(tmp_path / "clip.mp4"),
                                   max_seconds=2, speed=4)
    assert out["video"].endswith(".gif") and os.path.getsize(out["video"]) > 500


# ----------------------------------------------------------- reward + sprites
def test_abandon_penalty_charges_for_every_occupant_left_inside():
    pytest.importorskip("gymnasium")
    from ml.env import EvacuationEnv, RewardConfig

    def stay_only_return(abandon):
        env = EvacuationEnv(stages=[0], reward=RewardConfig(abandon=abandon))
        env.reset(seed=3)
        total, left = 0.0, len(env._session.victims)
        for _ in range(500):
            _, r, term, trunc, _ = env.step(0)
            total += r
            if term or trunc:
                return total, left
        raise AssertionError("a stay-only agent must hit the give-up rule")

    free, n = stay_only_return(0.0)
    charged, n2 = stay_only_return(100.0)
    assert n == n2 and n > 0
    assert charged == pytest.approx(free - 100.0 * n)


def test_give_up_and_timeout_penalties_apply_only_to_their_endings():
    pytest.importorskip("gymnasium")
    from ml.env import EvacuationEnv, RewardConfig

    def stay_return(cfg, max_seconds=240.0):
        env = EvacuationEnv(stages=[0], reward=cfg, max_sim_seconds=max_seconds)
        env.reset(seed=3)
        total = 0.0
        for _ in range(600):
            _, r, term, trunc, info = env.step(0)
            total += r
            if term or trunc:
                return total, info["summary"]["outcome"], trunc
        raise AssertionError("no ending")

    base, outcome, _ = stay_return(RewardConfig())
    assert outcome == "gave_up"
    charged, _, _ = stay_return(RewardConfig(give_up=200.0))
    assert charged == pytest.approx(base - 200.0)
    # a timeout penalty must not touch an ending that is not a timeout
    same, _, _ = stay_return(RewardConfig(timeout=200.0))
    assert same == pytest.approx(base)
    # ...and does apply when the clock runs out first
    cut, _, was_trunc = stay_return(RewardConfig(), max_seconds=3.0)
    cut_pen, _, _ = stay_return(RewardConfig(timeout=200.0), max_seconds=3.0)
    assert was_trunc and cut_pen == pytest.approx(cut - 200.0)


def test_victim_sprite_sets_are_cached_and_shared():
    from entities import victim
    names = [d for d in os.listdir(victim.ASSET_DIR)
             if os.path.isdir(os.path.join(victim.ASSET_DIR, d))]
    if not names:
        pytest.skip("no generated victim sprites in this checkout")
    a = victim._load_sprite_set(names[0])
    assert victim._load_sprite_set(names[0]) is a


# -------------------------------------------------------------- tiny training
def _load_train_script():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "tools", "train_agent.py")
    spec = importlib.util.spec_from_file_location("train_agent_script", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_train_script_parses_stage_lists():
    parse = _load_train_script().parse_stages
    assert parse("1-3", 10) == [0, 1, 2]
    assert parse("1,4,7-8", 10) == [0, 3, 6, 7]
    assert parse("none", 10) == [] and parse("", 10) == []
    with pytest.raises(SystemExit):
        parse("11", 10)


@pytest.mark.skipif(not HAVE_SB3, reason="stable-baselines3 / gymnasium not installed")
def test_a_tiny_real_training_run_leaves_a_complete_record(tmp_path):
    """The whole loop with real stable-baselines3: train a few epochs, validate
    against A*, checkpoint, record, report, then the fresh-seed final test."""
    from ml import training
    from ml.policy import load_policy
    run = str(tmp_path / "run")
    env = training.make_train_env([0], n_envs=1, seed=0, max_seconds=15)
    model = training.make_model("maskable", env, seed=0, n_steps=64, batch_size=32,
                                update_epochs=1, net_arch=(16,))
    monitor = training.TrainingMonitor(
        run, train_stages=[0], heldout_stages=[1], eval_every=100, eval_episodes=1,
        max_seconds=15, record_every=1, record_stages=[0], video_speed=8)
    model.learn(total_timesteps=256, callback=monitor)
    env.close()
    model.save(os.path.join(run, "final_model"))

    epochs = read_csv(os.path.join(run, "epochs.csv"))
    assert [r["epoch"] for r in epochs] == list(range(1, len(epochs) + 1)) and len(epochs) >= 3
    assert all(r["timesteps"] > 0 for r in epochs)
    assert epochs[-1]["value_loss"] is not None and epochs[-1]["entropy"] is not None
    assert epochs[-1]["train_accuracy"] is not None           # epoch vs accuracy is logged

    evals = read_csv(os.path.join(run, "evaluations.csv"))
    assert {(r["agent"], r["split"]) for r in evals} >= {
        ("astar", "train"), ("astar", "heldout"), ("model", "train"), ("model", "heldout")}
    assert evals[0]["epoch"] == 0 and evals[0]["timesteps"] == 0     # the untrained start
    assert all(0 <= r["accuracy_lo"] <= r["accuracy"] <= r["accuracy_hi"] <= 1 for r in evals)

    assert os.path.isfile(os.path.join(run, "best_model.zip"))
    assert any(f.startswith("step_") for f in os.listdir(os.path.join(run, "checkpoints")))
    assert any(f.startswith("astar_") for f in os.listdir(os.path.join(run, "videos")))
    assert any(f.startswith("step_") for f in os.listdir(os.path.join(run, "videos")))
    assert os.path.isfile(os.path.join(run, "report.html"))

    # a saved model loads through the game's own loader and answers
    policy = load_policy(os.path.join(run, "best_model.zip"))
    import numpy as np
    from ml.observation import OBS_SIZE, N_ACTIONS
    assert 0 <= policy.act(np.zeros(OBS_SIZE, np.float32), np.ones(N_ACTIONS, bool)) < N_ACTIONS

    text = training.final_test(run, os.path.join(run, "best_model.zip"),
                               os.path.join(run, "final_model.zip"),
                               [0], [1], episodes=1, max_seconds=15, workers=1,
                               log=lambda *a: None)
    assert "astar" in text and "best" in text and "final" in text
    assert os.path.isfile(os.path.join(run, "final_report.txt"))


@pytest.mark.skipif(not HAVE_SB3, reason="stable-baselines3 / gymnasium not installed")
def test_training_env_reports_raw_game_numbers_not_scaled_ones():
    """Reward scaling is for the optimiser only: the logged episode return
    (Monitor) and the game summary must stay in real game points."""
    from ml import training
    env = training.make_train_env([0], n_envs=1, seed=0, max_seconds=15)
    env.reset()
    info = {}
    for _ in range(400):
        _, _, dones, infos = env.step([0])
        if dones[0]:
            info = infos[0]
            break
    env.close()
    assert "summary" in info and info["summary"]["outcome"] in ("gave_up", "timeout")
    assert info["episode"]["r"] < 0 and abs(info["episode"]["r"]) < 50    # raw, not normalised
