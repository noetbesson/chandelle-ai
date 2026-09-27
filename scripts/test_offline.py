"""Run every regression with socket connections forbidden, regardless of local keys."""

def main():
    from pathlib import Path
    import os
    import socket
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    os.chdir(Path(__file__).resolve().parents[1])
    os.environ['OPENAI_ENABLED']='0'
    os.environ['REELS_LIVE_ENABLED']='0'
    os.environ['REELS_NORMALIZATION_BACKEND']='local'
    os.environ['PROACTIVE_SCHEDULER_ENABLED']='0'
    os.environ['PROACTIVE_MOOD_OPENAI']='0'
    os.environ['DATE_SCORING_BACKEND']='local'
    if sys.platform == 'win32':
        # Asyncio needs a private socket pair on Windows. Only this internally
        # created loopback pair bypasses the network guard, never API clients.
        connect = socket.socket.connect
        class InternalSocket(socket.socket):
            def connect(self, address):
                return connect(self, address)
        def internal_pair(*args, **kwargs):
            with InternalSocket() as listener:
                listener.bind(('127.0.0.1', 0))
                listener.listen(1)
                client = InternalSocket()
                client.connect(listener.getsockname())
                server, _ = listener.accept()
                return server, client
        socket.socketpair = internal_pair
    os.environ.pop('RUN_LIVE_OPENAI_SMOKE',None)
    def denied(*args,**kwargs):
        raise AssertionError('Network connections are forbidden during the default full suite')
    socket.socket.connect=denied
    socket.socket.connect_ex=denied
    socket.create_connection=denied
    import pytest
    return pytest.main(['-q','-p','no:cacheprovider',*sys.argv[1:]])

if __name__=='__main__':
    raise SystemExit(main())
