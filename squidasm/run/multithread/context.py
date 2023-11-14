from typing import Dict

from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.classical_communication.socket import Socket
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.run import Context as NetQASMContext

from squidasm.nqasm.multithread import NetSquidConnection

class SquidASMContext(NetQASMContext):
    def __init__(
        self,
        program_name: str,
    ):
        self._connection = NetSquidConnection(
            app_name=program_name,
        )

    @property
    def connection(self) -> BaseNetQASMConnection:
        return self._connection

    @property
    def csockets(self) -> Dict[str, Socket]:
        raise NotImplementedError

    @property
    def epr_sockets(self) -> Dict[str, EPRSocket]:
        raise NotImplementedError
