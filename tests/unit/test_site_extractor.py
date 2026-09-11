"""Unit tests for Site Characterizer (src/analysis/site_extractor.py)."""

import pytest
from src.frontend.cfg_builder import build_cfgs
from src.frontend.call_graph import build_call_graph
from src.analysis.alias_resolver import AliasResolver
from src.analysis.lockset_analyzer import LocksetAnalyzer
from src.analysis.site_extractor import SiteExtractor


def test_lock_site_extraction_basic():
    """Verify basic lock site extraction and identification of lock/unlock lines."""
    ir = """
    define void @foo(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cg = build_call_graph(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)
    lockset_analyzer = LocksetAnalyzer(resolver)

    extractor = SiteExtractor(resolver, cg, lockset_analyzer)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 1
    site = sites[0]
    assert site.site_id == "s1"
    assert site.function == "foo"
    assert site.mutex_canonical_id == "%m"


def test_direct_reads_and_writes():
    """Verify direct memory reads (load) and writes (store) in critical section are extracted."""
    ir = """
    @global_var = global i32 0, align 4

    define void @foo(i8* %m, i32* %ptr) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        %val = load i32, i32* @global_var
        store i32 42, i32* %ptr
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cg = build_call_graph(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)
    lockset_analyzer = LocksetAnalyzer(resolver)

    extractor = SiteExtractor(resolver, cg, lockset_analyzer)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 1
    site = sites[0]
    assert "@global_var" in site.reads
    assert "%ptr" in site.writes


def test_transitive_memory_effects():
    """Verify transitive reads and writes of called helper functions are aggregated."""
    ir = """
    @global_read = global i32 0, align 4
    @global_write = global i32 0, align 4

    define void @helper() {
    entry:
        %v = load i32, i32* @global_read
        store i32 %v, i32* @global_write
        ret void
    }

    define void @foo(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call void @helper()
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cg = build_call_graph(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)
    lockset_analyzer = LocksetAnalyzer(resolver)

    extractor = SiteExtractor(resolver, cg, lockset_analyzer)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 1
    site = sites[0]
    assert "helper" in site.calls
    assert "@global_read" in site.transitive_reads
    assert "@global_write" in site.transitive_writes


def test_indirect_call_flag():
    """Verify calling a function pointer inside critical section sets has_indirect_calls = True."""
    ir = """
    define void @foo(i8* %m, void ()* %fn_ptr) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call void %fn_ptr()
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cg = build_call_graph(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)
    lockset_analyzer = LocksetAnalyzer(resolver)

    extractor = SiteExtractor(resolver, cg, lockset_analyzer)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 1
    site = sites[0]
    assert site.has_indirect_calls is True


def test_lockset_at_entry_extraction():
    """Verify lockset_at_entry records outer parent locks already held."""
    ir = """
    define void @foo(i8* %m1, i8* %m2) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m1)
        call i32 @pthread_mutex_lock(i8* %m2)
        call i32 @pthread_mutex_unlock(i8* %m2)
        call i32 @pthread_mutex_unlock(i8* %m1)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cg = build_call_graph(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)
    lockset_analyzer = LocksetAnalyzer(resolver)

    extractor = SiteExtractor(resolver, cg, lockset_analyzer)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 2
    site1, site2 = sites[0], sites[1]
    assert site1.mutex_canonical_id == "%m1"
    assert site1.lockset_at_entry == frozenset()
    assert site2.mutex_canonical_id == "%m2"
    assert site2.lockset_at_entry == frozenset(["%m1"])


def test_atomic_and_memcpy_effects():
    """Verify atomicrmw, cmpxchg, llvm.memcpy, and llvm.memset memory effects in critical section."""
    ir = """
    @atomic_cnt = global i32 0, align 4
    @src_buf = global [16 x i8] zeroinitializer, align 1
    @dst_buf = global [16 x i8] zeroinitializer, align 1

    define void @foo(i8* %m, ptr %ptr) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        %old = atomicrmw add ptr @atomic_cnt, i32 1 seq_cst
        call void @llvm.memcpy.p0.p0.i64(ptr @dst_buf, ptr @src_buf, i64 16, i1 false)
        call void @llvm.memset.p0.i64(ptr %ptr, i8 0, i64 8, i1 false)
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cg = build_call_graph(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)
    lockset_analyzer = LocksetAnalyzer(resolver)

    extractor = SiteExtractor(resolver, cg, lockset_analyzer)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 1
    site = sites[0]
    # atomicrmw writes and reads
    assert "@atomic_cnt" in site.reads
    assert "@atomic_cnt" in site.writes
    # memcpy reads src, writes dst
    assert "@src_buf" in site.reads
    assert "@dst_buf" in site.writes
    # memset writes ptr
    assert "%ptr" in site.writes


def test_inline_asm_and_fence_effects():
    """Verify inline assembly and fence (RCU memory barriers) are extracted as hardware effects."""
    ir = """
    define void @foo(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call void asm sideeffect "outb %al, %w1", "{ax},N{dirflag},..."()
        fence seq_cst
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cg = build_call_graph(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)
    lockset_analyzer = LocksetAnalyzer(resolver)

    extractor = SiteExtractor(resolver, cg, lockset_analyzer)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 1
    site = sites[0]
    # Check that inline asm flagged the site
    assert site.has_inline_asm is True
    # Check that fence flagged the site
    assert site.has_memory_intrinsic is True


# ---------------------------------------------------------------------------
# Tests for _mark_single_thread_sites
# ---------------------------------------------------------------------------

def _build_extractor(ir: str):
    """Helper: parse IR and build a ready SiteExtractor + cfgs pair."""
    cfgs = build_cfgs(ir)
    cg = build_call_graph(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)
    lockset_analyzer = LocksetAnalyzer(resolver)
    extractor = SiteExtractor(resolver, cg, lockset_analyzer)
    return extractor, cfgs


def test_single_thread_no_pthread_create():
    """When no pthread_create call exists, no site should be marked single-threaded
    (conservative: we cannot prove the program is sequential)."""
    ir = """
    define void @worker(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }
    """
    extractor, cfgs = _build_extractor(ir)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 1
    # No pthread_create => conservative: nothing marked single-threaded
    assert sites[0].is_single_thread is False


def test_single_thread_lock_in_thread_entry():
    """A lock site inside the thread-entry function itself must NOT be marked
    single-threaded — it executes in a new thread."""
    ir = """
    define void @thread_fn(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }

    define void @main_fn(i8* %m) {
    entry:
        call i32 @pthread_create(i8* null, i8* null, i8* (i8*)* @thread_fn, i8* %m)
        ret void
    }
    """
    extractor, cfgs = _build_extractor(ir)
    sites = extractor.extract_sites(cfgs)

    # The lock is in @thread_fn which is a thread entry -> not single-threaded
    assert len(sites) == 1
    assert sites[0].function == "thread_fn"
    assert sites[0].is_single_thread is False


def test_single_thread_lock_before_spawn():
    """A lock site in a function that is never reachable from any thread entry
    should be marked is_single_thread = True."""
    ir = """
    define void @init(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }

    define void @thread_fn(i8* %arg) {
    entry:
        ret void
    }

    define void @main_fn(i8* %m) {
    entry:
        call void @init(i8* %m)
        call i32 @pthread_create(i8* null, i8* null, i8* (i8*)* @thread_fn, i8* null)
        ret void
    }
    """
    extractor, cfgs = _build_extractor(ir)
    sites = extractor.extract_sites(cfgs)

    # @init is only called before thread spawn and is not reachable from @thread_fn
    assert len(sites) == 1
    assert sites[0].function == "init"
    assert sites[0].is_single_thread is True


def test_single_thread_transitively_reachable_from_thread():
    """A lock in a helper called (transitively) from the thread entry must NOT
    be marked single-threaded."""
    ir = """
    define void @do_work(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }

    define void @thread_fn(i8* %m) {
    entry:
        call void @do_work(i8* %m)
        ret void
    }

    define void @main_fn(i8* %m) {
    entry:
        call i32 @pthread_create(i8* null, i8* null, i8* (i8*)* @thread_fn, i8* %m)
        ret void
    }
    """
    extractor, cfgs = _build_extractor(ir)
    sites = extractor.extract_sites(cfgs)

    # @do_work is transitively reachable from @thread_fn -> not single-threaded
    assert len(sites) == 1
    assert sites[0].function == "do_work"
    assert sites[0].is_single_thread is False


def test_single_thread_mixed_sites():
    """With both a pre-spawn init lock and a thread-only lock, only the init
    site should be flagged single-threaded."""
    ir = """
    define void @thread_work(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }

    define void @thread_fn(i8* %m) {
    entry:
        call void @thread_work(i8* %m)
        ret void
    }

    define void @setup(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }

    define void @main_fn(i8* %m) {
    entry:
        call void @setup(i8* %m)
        call i32 @pthread_create(i8* null, i8* null, i8* (i8*)* @thread_fn, i8* %m)
        ret void
    }
    """
    extractor, cfgs = _build_extractor(ir)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 2
    sites_by_func = {s.function: s for s in sites}

    # @setup is not reachable from any thread entry
    assert sites_by_func["setup"].is_single_thread is True
    # @thread_work is transitively reached from @thread_fn
    assert sites_by_func["thread_work"].is_single_thread is False


def test_single_thread_multiple_thread_entries():
    """With two pthread_create calls pointing to different entry functions,
    functions reachable from either should NOT be flagged."""
    ir = """
    define void @worker_a(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }

    define void @worker_b(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }

    define void @main_fn(i8* %m) {
    entry:
        call i32 @pthread_create(i8* null, i8* null, i8* (i8*)* @worker_a, i8* %m)
        call i32 @pthread_create(i8* null, i8* null, i8* (i8*)* @worker_b, i8* %m)
        ret void
    }
    """
    extractor, cfgs = _build_extractor(ir)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 2
    for site in sites:
        assert site.is_single_thread is False, (
            f"Site in {site.function} incorrectly marked single-threaded"
        )


def test_single_thread_thrd_create_c11():
    """_mark_single_thread_sites must also recognise C11 thrd_create as a
    thread-spawn API."""
    ir = """
    define void @thread_fn(i8* %arg) {
    entry:
        ret void
    }

    define void @init(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }

    define void @main_fn(i8* %m) {
    entry:
        call void @init(i8* %m)
        call i32 @thrd_create(i8* null, i8* (i8*)* @thread_fn, i8* null)
        ret void
    }
    """
    extractor, cfgs = _build_extractor(ir)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 1
    # @init is not reachable from @thread_fn, so it should be single-threaded
    assert sites[0].function == "init"
    assert sites[0].is_single_thread is True


def test_single_thread_uv_thread_create():
    """_mark_single_thread_sites must recognise uv_thread_create (libuv) as well."""
    ir = """
    define void @uv_worker(i8* %arg) {
    entry:
        ret void
    }

    define void @pre_init(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }

    define void @start(i8* %m) {
    entry:
        call void @pre_init(i8* %m)
        call i32 @uv_thread_create(i8* null, i8* (i8*)* @uv_worker, i8* null)
        ret void
    }
    """
    extractor, cfgs = _build_extractor(ir)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 1
    assert sites[0].function == "pre_init"
    assert sites[0].is_single_thread is True

