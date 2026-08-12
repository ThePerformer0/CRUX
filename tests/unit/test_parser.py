"""Unit tests for LLVM IR text parser (src/frontend/parser.py)."""

import pytest
from src.frontend.parser import parse_instruction, LLVMInstruction


def test_parse_instruction_dest_op():
    """Verify destination, opcode, and arguments parsing for assignment instructions."""
    raw = "  %1 = alloca i32, align 4"
    inst = parse_instruction(raw, line_number=10)
    assert inst.dest == "%1"
    assert inst.opcode == "alloca"
    assert inst.line_number == 10


def test_parse_store_instruction():
    """Verify instruction parsing for void operations without destination (store)."""
    raw = "  store i32 42, i32* %ptr, align 4"
    inst = parse_instruction(raw, line_number=15)
    assert inst.dest is None
    assert inst.opcode == "store"


def test_parse_phi_instruction():
    """Verify phi instruction parsing into phi_incoming tuples [(val, block)]."""
    raw = "  %res = phi i32 [ 10, %entry ], [ %val2, %loop_body ]"
    inst = parse_instruction(raw, line_number=20)
    assert inst.dest == "%res"
    assert inst.opcode == "phi"
    assert inst.phi_incoming == [("10", "entry"), ("%val2", "loop_body")]


def test_parse_call_instruction():
    """Verify call instruction parsing."""
    raw = "  %call = call i32 @pthread_mutex_lock(i8* %mutex)"
    inst = parse_instruction(raw, line_number=25)
    assert inst.dest == "%call"
    assert inst.opcode == "call"
