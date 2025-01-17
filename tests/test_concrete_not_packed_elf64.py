import angr
import claripy
import nose
import os
import subprocess
import logging

try:
    import avatar2
    from angr_targets import AvatarGDBConcreteTarget
except ImportError:
    raise nose.SkipTest()


binary_x64 = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                          os.path.join('..', '..', 'binaries', 'tests', 'x86_64', 'not_packed_elf64'))

GDB_SERVER_IP = '127.0.0.1'
GDB_SERVER_PORT = 9999


BINARY_OEP = 0x4009B2
BINARY_DECISION_ADDRESS = 0x400AF3
DROP_STAGE2_V1 = 0x400B87
DROP_STAGE2_V2 = 0x400BB6
VENV_DETECTED = 0x400BC2
FAKE_CC = 0x400BD6
BINARY_EXECUTION_END = 0x400C03


def setup_x64():
    subprocess.Popen("gdbserver %s:%s '%s'" % (GDB_SERVER_IP, GDB_SERVER_PORT, binary_x64), stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, shell=True)


avatar_gdb = None


def teardown():
    global avatar_gdb
    if avatar_gdb:
        avatar_gdb.exit()


@nose.with_setup(setup_x64, teardown)
def test_concrete_engine_linux_x64_simprocedures():
    global avatar_gdb
    # pylint: disable=no-member
    avatar_gdb = AvatarGDBConcreteTarget(avatar2.archs.x86.X86_64, GDB_SERVER_IP, GDB_SERVER_PORT)
    p = angr.Project(binary_x64, concrete_target=avatar_gdb, use_sim_procedures=True,
                     page_size=0x1000)
    entry_state = p.factory.entry_state()
    solv_concrete_engine_linux_x64(p, entry_state)


@nose.with_setup(setup_x64, teardown)
def test_concrete_engine_linux_x64_no_simprocedures():
    global avatar_gdb
    # pylint: disable=no-member
    avatar_gdb = AvatarGDBConcreteTarget(avatar2.archs.x86.X86_64, GDB_SERVER_IP, GDB_SERVER_PORT)
    p = angr.Project(binary_x64, concrete_target=avatar_gdb, use_sim_procedures=False,
                     page_size=0x1000)
    entry_state = p.factory.entry_state()
    solv_concrete_engine_linux_x64(p, entry_state)


@nose.with_setup(setup_x64, teardown)
def test_concrete_engine_linux_x64_unicorn_simprocedures():
    global avatar_gdb
    # pylint: disable=no-member
    avatar_gdb = AvatarGDBConcreteTarget(avatar2.archs.x86.X86_64, GDB_SERVER_IP, GDB_SERVER_PORT)
    p = angr.Project(binary_x64, concrete_target=avatar_gdb, use_sim_procedures=True,
                     page_size=0x1000)
    entry_state = p.factory.entry_state(add_options=angr.options.unicorn)
    solv_concrete_engine_linux_x64(p, entry_state)


@nose.with_setup(setup_x64, teardown)
def test_concrete_engine_linux_x64_unicorn_no_simprocedures():
    global avatar_gdb
    # pylint: disable=no-member
    avatar_gdb = AvatarGDBConcreteTarget(avatar2.archs.x86.X86_64, GDB_SERVER_IP, GDB_SERVER_PORT)
    p = angr.Project(binary_x64, concrete_target=avatar_gdb, use_sim_procedures=False,
                     page_size=0x1000)
    entry_state = p.factory.entry_state(add_options=angr.options.unicorn)
    solv_concrete_engine_linux_x64(p, entry_state)


def execute_concretly(project, state, address, concretize):
    simgr = project.factory.simgr(state)
    simgr.use_technique(angr.exploration_techniques.Symbion(find=[address], concretize=concretize))
    exploration = simgr.run()
    return exploration.stashes['found'][0]


def solv_concrete_engine_linux_x64(p, state):
    new_concrete_state = execute_concretly(p, state, BINARY_DECISION_ADDRESS, [])

    arg0 = claripy.BVS('arg0', 8*32)
    symbolic_buffer_address = new_concrete_state.regs.rbp-0xc0
    new_concrete_state.memory.store(symbolic_buffer_address, arg0)

    # symbolic exploration
    simgr = p.factory.simgr(new_concrete_state)
    exploration = simgr.explore(find=DROP_STAGE2_V2, avoid=[DROP_STAGE2_V1, VENV_DETECTED, FAKE_CC])
    if not exploration.stashes['found'] and exploration.errored and type(exploration.errored[0].error) is angr.errors.SimIRSBNoDecodeError:
        raise nose.SkipTest()
    new_symbolic_state = exploration.stashes['found'][0]

    execute_concretly(p, new_symbolic_state, BINARY_EXECUTION_END, [(symbolic_buffer_address, arg0)])

    binary_configuration = new_symbolic_state.solver.eval(arg0, cast_to=int)

    correct_solution = 0xa00000006000000f6ffffff0000000000000000000000000000000000000000

    nose.tools.assert_true(binary_configuration == correct_solution)

def run_all():
    functions = globals()
    all_functions = dict(filter((lambda kv: kv[0].startswith('test_')), functions.items()))
    for f in sorted(all_functions.keys()):
        if hasattr(all_functions[f], '__call__'):
            if hasattr(all_functions[f], 'setup'):
                all_functions[f].setup()
            try:
                all_functions[f]()
            finally:
                if hasattr(all_functions[f], 'teardown'):
                    all_functions[f].teardown()

if __name__ == "__main__":
    logging.getLogger("identifier").setLevel("DEBUG")
    import sys
    if len(sys.argv) > 1:
        globals()['test_' + sys.argv[1]]()
    else:
        run_all()
