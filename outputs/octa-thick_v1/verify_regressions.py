"""Run existing reviewer regressions without changing its code or settings."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import engine  # activated environment DLL guard + existing code import path
import unittest

if __name__ == '__main__':
    suite=unittest.defaultTestLoader.loadTestsFromNames([
        'octa_seg_v1.test_reviewer', 'octa_seg_v1.test_ilm_preview'])
    with (engine.HERE/'verification/regressions.txt').open('w') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    print(f'{result.testsRun} reviewer regression checks; successful={result.wasSuccessful()}')
    raise SystemExit(0 if result.wasSuccessful() else 1)
