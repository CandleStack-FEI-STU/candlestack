"""ML: the models users upload, their files and the checks of an upload.

Other modules import only from here (``from candlestack.ml import models_router``), never from
the submodules. Nothing here imports Keras or TensorFlow: an upload is checked by reading the
file (its ``config.json`` and weights), not by loading it.
"""

from candlestack.ml.api import router as models_router
from candlestack.ml.schemas import ModelOut, ModelsOut

__all__ = ["ModelOut", "ModelsOut", "models_router"]
