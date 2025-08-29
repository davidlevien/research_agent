"""Deterministic seeding for reproducible outputs."""

import os
import random
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Default seed for reproducible results
DEFAULT_SEED = 2025

def set_global_seeds(seed: Optional[int] = None) -> int:
    """
    Set global random seeds for reproducible behavior.
    
    Args:
        seed: Seed value to use. If None, uses DEFAULT_SEED.
        
    Returns:
        The seed value that was set
    """
    if seed is None:
        seed = DEFAULT_SEED
    
    # Set environment variable for hash randomization
    os.environ["PYTHONHASHSEED"] = str(seed)
    
    # Set Python random seed
    random.seed(seed)
    
    # Set numpy seed if available
    try:
        import numpy as np
        np.random.seed(seed)
        logger.debug(f"Set numpy random seed to {seed}")
    except ImportError:
        logger.debug("NumPy not available, skipping numpy seed setting")
    
    # Set torch seed if available
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
        logger.debug(f"Set torch random seed to {seed}")
    except ImportError:
        logger.debug("PyTorch not available, skipping torch seed setting")
    
    # Set tensorflow seed if available
    try:
        import tensorflow as tf
        tf.random.set_seed(seed)
        logger.debug(f"Set tensorflow random seed to {seed}")
    except ImportError:
        logger.debug("TensorFlow not available, skipping tensorflow seed setting")
    
    logger.info(f"Set global random seeds to {seed}")
    return seed

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