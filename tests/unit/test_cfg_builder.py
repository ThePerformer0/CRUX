"""Unit tests for CFG builder (src/frontend/cfg_builder.py)."""

import pytest
from src.frontend.cfg_builder import build_cfgs, CFG, BasicBlock


def test_basic_block_split():
    """Verify function is split into basic blocks according to label boundaries."""
    ir = """
    define i32 @test_func(i32 %cond) {
    entry:
        %cmp = icmp eq i32 %cond, 0
        br i1 %cmp, label %if_true, label %if_false

    if_true:
        ret i32 1

    if_false:
        ret i32 0
    }
    """
    cfgs = build_cfgs(ir)
    assert "test_func" in cfgs
    cfg = cfgs["test_func"]
    assert cfg.entry_block == "entry"
    assert set(cfg.blocks.keys()) == {"entry", "if_true", "if_false"}


def test_unconditional_branch():
    """Verify unconditional branch (br label %target) sets single successor."""
    ir = """
    define void @uncond() {
    entry:
        br label %target
    target:
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cfg = cfgs["uncond"]
    assert cfg.blocks["entry"].successors == ["target"]
    assert cfg.blocks["target"].predecessors == ["entry"]


def test_conditional_branch():
    """Verify conditional branch (br i1 %cond, label %A, label %B) sets both successors."""
    ir = """
    define void @cond_br(i1 %c) {
    entry:
        br i1 %c, label %then, label %else
    then:
        ret void
    else:
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cfg = cfgs["cond_br"]
    assert cfg.blocks["entry"].successors == ["then", "else"]
    assert cfg.blocks["then"].predecessors == ["entry"]
    assert cfg.blocks["else"].predecessors == ["entry"]


def test_switch_terminator():
    """Verify switch instruction extracts default and case target labels."""
    ir = """
    define void @switch_func(i32 %val) {
    entry:
        switch i32 %val, label %default [
            i32 1, label %case1
            i32 2, label %case2
        ]
    default:
        ret void
    case1:
        ret void
    case2:
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cfg = cfgs["switch_func"]
    succs = cfg.blocks["entry"].successors
    assert set(succs) == {"default", "case1", "case2"}


def test_invoke_successors():
    """Verify invoke instruction sets normal and unwind label successors."""
    ir = """
    define void @invoke_demo() {
    entry:
        invoke void @may_throw() to label %normal unwind label %catch
    normal:
        ret void
    catch:
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cfg = cfgs["invoke_demo"]
    assert cfg.blocks["entry"].successors == ["normal", "catch"]
    assert cfg.blocks["normal"].predecessors == ["entry"]
    assert cfg.blocks["catch"].predecessors == ["entry"]


def test_predecessors_computation():
    """Verify predecessor lists are computed correctly across converging control flow."""
    ir = """
    define void @converge(i1 %c) {
    entry:
        br i1 %c, label %b1, label %b2
    b1:
        br label %merge
    b2:
        br label %merge
    merge:
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cfg = cfgs["converge"]
    assert set(cfg.blocks["merge"].predecessors) == {"b1", "b2"}
