from collections.abc import Callable
from pathlib import Path
from typing import TypeAlias

from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.storage import Storage

StorageFactory: TypeAlias = Callable[[Path], Storage]

MirrorFactory = Callable[..., BandersnatchMirror]
