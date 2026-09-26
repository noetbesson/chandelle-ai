"""Run every regression with socket connections forbidden, regardless of local keys."""

def main():
    from pathlib import Path
    import os
    import socket
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    os.chdir(Path(__file__).resolve().parents[1])
    os.environ['OPENAI_ENABLED']='0'
    os.environ['GRADIUM_ENABLED']='0'
    os.environ.pop('RUN_LIVE_OPENAI_SMOKE',None)
    def denied(*args,**kwargs):
        raise AssertionError('Network connections are forbidden during the default full suite')
    socket.socket.connect=denied
    socket.socket.connect_ex=denied
    socket.create_connection=denied
    import pytest
    return pytest.main(['-q','-p','no:cacheprovider'])

if __name__=='__main__':
    raise SystemExit(main())
