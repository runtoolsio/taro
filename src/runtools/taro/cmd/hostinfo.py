import runtools.runcore.util.hostinfo


def run(args):
    # Use `show` argument: taro host info show
    host_info = runtools.runcore.util.hostinfo.read_hostinfo()
    for name, value in host_info.items():
        print(f"{name}: {value}")
