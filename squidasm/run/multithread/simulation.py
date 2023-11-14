import os
from typing import Any, Dict, List, Callable

from netqasm.runtime import env
from netqasm.runtime.application import Application, Program, ApplicationInstance
from netqasm.runtime.interface.config import parse_network_config
from netqasm.sdk.config import LogConfig
from netqasm.sdk.run import Context as NetQASMContext, Program as NetQASMProgram
from netqasm.sdk.shared_memory import SharedMemoryManager
from netqasm.util.yaml import dump_yaml, load_yaml

from netsquid import QFormalism

from squidasm.run.multithread import SquidAsmRuntimeManager, SquidASMContext
from squidasm.util.module import import_module_from_file_path

class Simulation:
    def __init__(
        self,
        app_dir: str,
        logging_enabled: bool = True,
    ):
        # Configure app directory.
        self._app_dir = app_dir

        if not os.path.exists(app_dir):
            raise FileNotFoundError(f'App directory `{app_dir}` does not exist.')

        # Configure logging.
        self._log_config = None
        self._logging_enabled = logging_enabled

        if self._logging_enabled:
            log_dir = env.get_log_dir(self._app_dir)

            self._log_config = LogConfig(
                app_dir=self._app_dir,
                log_dir=log_dir,
                track_lines=True,
            )

        # TODO: error handling
        # Configure network.
        network_config_yaml = load_yaml(os.path.join(self._app_dir, 'config', 'network.yaml'))
        self._network_config = parse_network_config(network_config_yaml)

        if self._network_config is None:
            raise FileNotFoundError('Missing network configuration file.')

        # Configure runtime manager.
        self._manager = SquidAsmRuntimeManager()
        self._manager.netsquid_formalism = QFormalism.KET
        self._manager.set_network(
            cfg=self._network_config
        )

    def configure(self):
        raise NotImplementedError()

    def run(
        self,
        num_rounds: int = 1,
    ) -> List[Dict[str, Any]]:
        self._manager.start_backend()

        # The application instance also initiates NetQASMConnections. This must
        # take place after the backend is started.
        app_instance = self._create_app_instance()

        results = []

        for _ in range(num_rounds):
            run_log_dir = None

            # Create timestamped directory for next run.
            if self._logging_enabled:
                assert self._log_config is not None
                run_log_dir = env.get_timed_log_dir(self._log_config.log_dir)

                self._manager.backend_log_dir = run_log_dir

                assert app_instance.logging_cfg is not None
                app_instance.logging_cfg.log_subroutines_dir = run_log_dir
                app_instance.logging_cfg.comm_log_dir = run_log_dir

            # Run the simulated application and save the result.
            result = self._manager.run_app(
                app_instance=app_instance,
                use_app_config=False,
            )
            results.append(result)

            # Save intermediate results in timestamped directory.
            if self._logging_enabled:
                assert run_log_dir is not None
                dump_yaml(
                    data=results,
                    file_path=os.path.join(run_log_dir, 'results.yaml'),
                )

            SharedMemoryManager.reset_memories()

        self._manager.stop_backend()

        return results

    def _create_app_instance(self) -> ApplicationInstance:
        programs = []

        # TODO: error handling
        self._application_config = load_yaml(os.path.join(self._app_dir, 'config', 'application.yaml'))

        roles = list(self._application_config.keys())

        for role in roles:
            program_instance = self._create_program_instance(role)
            programs += [program_instance]

        application = Application(
            programs=programs,
            metadata=None,
        )
        program_inputs=dict(zip(roles, [{} for _ in roles]))

        # TODO: error handling
        node_mapping = load_yaml(os.path.join(self._app_dir, 'config', 'roles.yaml'))

        return ApplicationInstance(
            app=application,
            program_inputs=program_inputs,
            party_alloc=node_mapping,
            network=self._network_config,
            logging_cfg=self._log_config,
        )

    def _create_program_instance(
        self,
        role: str,
    ) -> Program:
        ctor = self._get_program_ctor(role)

        # TODO: error handling
        inputs = load_yaml(os.path.join(self._app_dir, 'config', f'{role}.yaml'))

        def run_program_instance() -> Dict[str, Any]:
            program: NetQASMProgram = ctor(**inputs)
            context: NetQASMContext = SquidASMContext(
                program_name=role,
            )

            results = {}
            with context.connection:
                results = program.run(context)
            return results

        return Program(
            party=role,
            entry=run_program_instance,
            args=inputs.keys(),
            results=[],
        )

    def _get_program_ctor(
        self,
        role: str,
    ) -> Callable[..., NetQASMProgram]:
        # TODO: validation

        src_file = self._application_config[role]['src_file']
        class_name = self._application_config[role]['class_name']

        module_name = src_file[:-3]
        module_path = os.path.join(self._app_dir, 'src', src_file)
        module = import_module_from_file_path(module_name, module_path)

        return getattr(module, class_name)
