import argparse
import asyncio
import os
import importlib
import json
import re
import sys
import http.server
import socket
import socketserver
import threading
from dv_flow.mgr import PackageLoader, TaskGraphBuilder, TaskDataInput, TaskRunCtxt

def parse_with_string(with_str):
    """Parse a with string containing semicolon-separated key/value pairs.
    Values can be quoted strings or semicolon-separated lists.
    Example: 'include=top1.v;top2.v;type="systemVerilogSource"'
    """
    if not with_str:
        return {}
    
    result = {}
    current_key = None
    current_values = []
    
    # Split by semicolon but preserve quoted content
    parts = re.split(';(?=(?:[^"]*"[^"]*")*[^"]*$)', with_str)
    
    for part in parts:
        part = part.strip()
        if '=' in part:
            # If we have a key-value pair
            if current_key and current_values:
                # Store previous key's values if any
                result[current_key] = current_values[0] if len(current_values) == 1 else current_values
            
            # Start new key-value pair
            key, value = part.split('=', 1)
            current_key = key.strip()
            current_values = []
            
            # Handle the value
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                # Quoted string - store as single value
                current_values.append(value[1:-1])
            else:
                current_values.append(value)
        else:
            # This is a continuation value for the current key
            if current_key:  # Only append if we have a current key
                if part.startswith('"') and part.endswith('"'):
                    current_values.append(part[1:-1])
                else:
                    current_values.append(part)
    
    # Store the last key's values
    if current_key and current_values:
        result[current_key] = current_values[0] if len(current_values) == 1 else current_values
                
    return result

def mk_run_spec_cmd(args):

    with open(args.spec, 'r') as spec_file:
        spec_data = json.load(spec_file)

    loader = PackageLoader()

    # Parse the with string if present
    with_params = {}
    if "with" in spec_data:
        with_params = parse_with_string(spec_data["with"])

    builder = TaskGraphBuilder(root_pkg=None, rundir=spec_data["rundir"], loader=loader)
    # Pass with parameters directly to mkTaskNode
    node = builder.mkTaskNode(spec_data["type"], **with_params)

    run_json = {
        "name": spec_data["name"],
        "rundir": spec_data["rundir"],
        "srcdir": spec_data["srcdir"],
    }

    run_json["inputs"] = spec_data["needs"].split(';')
    run_json["params"] = node.params.model_dump()
    run_json["run"] = "%s.%s" % (type(node.task).__module__, type(node.task).__name__)
    run_json["run-args"] = node.task.model_dump()

    with open(args.output, 'w') as output_file:
        json.dump(run_json, output_file, indent=4)


#    print("node: %s" % node)

def run_spec_cmd(args):
    with open(args.run_spec, 'r') as run_spec_file:
        run_spec_data = json.load(run_spec_file)

    run_module = run_spec_data["run"][:run_spec_data["run"].rfind('.')]
    run_cls = run_spec_data["run"][run_spec_data["run"].rfind('.')+1:]

    mod = importlib.import_module(run_module)
    cls = getattr(mod, run_cls)

    task = cls(**run_spec_data["run-args"])

    class Params:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
    params = Params(**run_spec_data["params"])

    changed = False
    inputs=[]
    memento = None

    for task_output in run_spec_data["inputs"]:
        if task_output.strip() != "":
            with open(task_output, 'r') as input_file:
                input_data = json.load(input_file)
            for in_data in input_data["output"]:
                inputs.append(Params(**in_data))

    input = TaskDataInput(
        name=run_spec_data["name"],
        changed=changed,
        srcdir=run_spec_data["srcdir"],
        rundir=run_spec_data["rundir"],
        params=params,
        inputs=inputs,
        memento=memento
    )

    ctxt = TaskRunCtxt(
        None, 
        None, 
        run_spec_data["rundir"])

    result = asyncio.run(task(ctxt, input))

    result_file = "%s.json" % os.path.join(
        run_spec_data["rundir"],
        run_spec_data["name"])

    # TODO: must apply information (such as src, seq)

    with open(result_file, "w") as fp:
        json.dump(result.model_dump(), fp, indent=4)

    sys.exit(result.status)

def share_dir_cmd(args):
    cmake_dir = os.path.dirname(__file__)
    print(os.path.join(cmake_dir, "share"))

class MyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        data = json.loads(post_data.decode())

        if "command" in data.keys():
            cmd = data["command"].split()

            if cmd[0] == "cmake-mk-run-spec":
                class Args:
                    def __init__(self, **kwargs):
                        self.__dict__.update(kwargs)
                argv = {}
                argv["spec"] = cmd[1]
                argv["output"] = cmd[3]
                args = Args(**argv)
                mk_run_spec_cmd(args)


        # Send a response
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'POST request received')

def cmake_config_cmd(args):
    import subprocess

    builddir = args.builddir or "build"
    srcdir = args.srcdir or "."

    srcdir = os.path.abspath(srcdir)
    builddir = os.path.abspath(builddir)

    if not os.path.exists(builddir):
        os.makedirs(builddir)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 0))
    PORT = sock.getsockname()[1]
    sock.close()

    httpd = socketserver.TCPServer(("", PORT), MyHandler)

    def run_server():
        httpd.serve_forever()
    
    env = os.environ.copy()
    env["DFM_PORT"] = str(PORT)

    server = threading.Thread(target=run_server, daemon=True)
    server.start()

    cmd = ["cmake", "-S", srcdir, "-B", builddir]

    for gen in args.G or []:
        cmd.append("-G%s" % gen)
    for d in args.D or []:
        cmd.append("-D%s" % d)

    print("Running cmake config: %s" % ' '.join(cmd))
    
    result = subprocess.run(
        cmd, 
        cwd=builddir,
        env=env)

    httpd.shutdown()
    server.join()

    
    if result.returncode != 0:
        print("CMake configuration failed with exit code %d" % result.returncode)
        sys.exit(result.returncode)
    
    print("CMake configuration completed successfully.")



def dfm_add_utilcmd(subparsers):
    mk_run_spec = subparsers.add_parser('cmake-mk-run-spec', 
                                help='Creates a run-specification file')
    mk_run_spec.add_argument("spec", help="Specify implementation")
    mk_run_spec.add_argument("-o", "--output", help="Output filename")
    mk_run_spec.set_defaults(func=mk_run_spec_cmd)

    run_spec = subparsers.add_parser('cmake-run-spec',
                                    help='Display the run specification')
    run_spec.add_argument("run_spec", help="Run specification file")
    run_spec.add_argument("-s", "--status", help="Up-to-date marker")
    run_spec.set_defaults(func=run_spec_cmd)

def dfm_add_subcmd(subparsers):
    cmake_share_dir = subparsers.add_parser('cmake-share-dir',
                                            help='Display the cmake share directory')
    cmake_share_dir.set_defaults(func=share_dir_cmd)

    class MatchPrefix(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            name = option_string.lstrip('-')
            if not hasattr(namespace, name) or getattr(namespace, name) is None:
                setattr(namespace, name, [])
            getattr(namespace, name).append(values)
            print("option_string: %s (%s)" % (option_string, values), flush=True)

    cmake_config = subparsers.add_parser('cmake-config',
                                         help='Configure a cmake project')
    cmake_config.add_argument("-B", "--builddir", help="CMake build directory")
    cmake_config.add_argument("-S", "--srcdir", help="CMake source directory")
    cmake_config.add_argument("-D", 
                              action=MatchPrefix,
                              help="CMake defines")
    cmake_config.add_argument("-G", 
                              action=MatchPrefix,
                              help="CMake generator type")
    cmake_config.set_defaults(func=cmake_config_cmd)
