import os
import random
try:
    import numpy as np
except Exception:
    np = None
try:
    import torch
except Exception:
    torch = None

def set_global_seeds(seed_like="20230817"):
    # normalize any input (int/str/float) into a 32-bit integer
    s = str(seed_like)
    try:
        s_int = abs(hash(s)) % (2**31)
    except Exception:
        s_int = 1337
    random.seed(s_int)
    os.environ["PYTHONHASHSEED"] = str(s_int)
    if np is not None:
        np.random.seed(s_int)
    if torch is not None:
        torch.manual_seed(s_int)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(s_int)