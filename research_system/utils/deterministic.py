"""Deterministic seeding for reproducible outputs."""

import hashlib
import os
import time
import random
import logging
from typing import Optional, Union

logger = logging.getLogger(__name__)

# Default seed for reproducible results
DEFAULT_SEED = 2025

def _coerce_seed(seed_like: Optional[Union[int, str]]) -> int:
    """Convert various seed types to integer."""
    if seed_like is None:
        return int(time.time()) % (2**32)
    try:
        return int(seed_like)
    except (TypeError, ValueError):
        h = hashlib.sha256(str(seed_like).encode()).hexdigest()[:8]
        return int(h, 16)

def set_global_seeds(seed_like: Optional[Union[int, str]] = None):
    """
    Set global random seeds for reproducible behavior.
    
    Args:
        seed_like: Seed value to use. Can be int or string.
                   If string, will be hashed to create an integer seed.
                   If None, uses time-based seed.
    """
    seed = _coerce_seed(seed_like)
    
    # Set environment variable for hash randomization
    os.environ["PYTHONHASHSEED"] = str(seed)
    
    # Set Python random seed
    random.seed(seed)
    
    # Set numpy seed if available
    try:
        import numpy as np
        np.random.seed(seed)
    except Exception:
        pass
    
    # Set torch seed if available
    try:
        import torch
        torch.manual_seed(seed)
        try:
            torch.cuda.manual_seed_all(seed)
        except Exception:
            pass
    except Exception:
        pass
    
    logger.info("Global seed set to %s (from %r)", seed, seed_like)

def get_deterministic_random():
    """
    Get a random generator with deterministic behavior.
    
    Returns:
        A seeded random.Random instance
    """
    rng = random.Random()
    rng.seed(DEFAULT_SEED)
    return rng

def deterministic_sample(items, k: int, seed: Optional[int] = None):
    """
    Sample items deterministically.
    
    Args:
        items: Sequence to sample from
        k: Number of items to sample
        seed: Optional seed (uses DEFAULT_SEED if None)
        
    Returns:
        List of sampled items
    """
    if seed is None:
        seed = DEFAULT_SEED
    
    rng = random.Random(seed)
    return rng.sample(list(items), min(k, len(items)))

def deterministic_choice(items, seed: Optional[int] = None):
    """
    Choose an item deterministically.
    
    Args:
        items: Sequence to choose from
        seed: Optional seed (uses DEFAULT_SEED if None)
        
    Returns:
        Chosen item
    """
    if not items:
        raise ValueError("Cannot choose from empty sequence")
    
    if seed is None:
        seed = DEFAULT_SEED
    
    rng = random.Random(seed)
    return rng.choice(list(items))

def deterministic_shuffle(items, seed: Optional[int] = None):
    """
    Shuffle items deterministically.
    
    Args:
        items: List to shuffle (modified in-place)
        seed: Optional seed (uses DEFAULT_SEED if None)
        
    Returns:
        The shuffled list (same object as input)
    """
    if seed is None:
        seed = DEFAULT_SEED
    
    rng = random.Random(seed)
    rng.shuffle(items)
    return items

def hash_seed_from_string(s: str) -> int:
    """
    Generate a deterministic seed from a string.
    
    Args:
        s: String to hash
        
    Returns:
        Integer seed derived from the string
    """
    return hash(s) % (2**31 - 1)

def context_seeded_choice(items, context: str, base_seed: Optional[int] = None):
    """
    Choose an item using context-specific deterministic seeding.
    
    Args:
        items: Sequence to choose from
        context: Context string (e.g., topic, cluster key) for deterministic variation
        base_seed: Base seed to combine with context hash
        
    Returns:
        Chosen item
    """
    if not items:
        raise ValueError("Cannot choose from empty sequence")
    
    if base_seed is None:
        base_seed = DEFAULT_SEED
    
    # Combine base seed with context hash for deterministic but context-specific choice
    context_hash = hash_seed_from_string(context)
    combined_seed = (base_seed + context_hash) % (2**31 - 1)
    
    return deterministic_choice(items, seed=combined_seed)

def ensure_deterministic_environment():
    """
    Ensure the environment is set up for deterministic behavior.
    
    This function should be called early in the application lifecycle.
    """
    # Check if seeds are already set
    if "PYTHONHASHSEED" not in os.environ:
        set_global_seeds()
    else:
        logger.debug("Random seeds already configured via environment")
    
    # Additional deterministic settings for ML libraries
    try:
        import torch
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        logger.debug("Set PyTorch deterministic settings")
    except ImportError:
        pass
    
    try:
        os.environ['TF_DETERMINISTIC_OPS'] = '1'
        logger.debug("Set TensorFlow deterministic operations")
    except Exception:
        pass