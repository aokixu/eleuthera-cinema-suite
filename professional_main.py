if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    import sys
    if '--check-runtime' in sys.argv:
        from runtime_check import run
        raise SystemExit(run(sys.argv[sys.argv.index('--check-runtime')+1]))
    from suite import run_app
    raise SystemExit(run_app('professional'))
