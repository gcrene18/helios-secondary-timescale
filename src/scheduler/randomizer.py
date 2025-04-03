"""
Randomization strategies for avoiding detection during scraping.
"""
from typing import Optional, Callable
import random
import numpy as np
from datetime import timedelta

from ..core.logging import get_logger
from ..config.settings import settings

logger = get_logger(__name__)

class RandomizationStrategy:
    """
    Implements various randomization strategies for scraping.
    
    This class provides methods to generate random intervals and delays
    to make scraping patterns less predictable and avoid detection.
    """
    
    @staticmethod
    def uniform_interval(base_interval: float, min_factor: float = None, max_factor: float = None) -> float:
        """
        Generate a randomized interval using uniform distribution.
        
        Args:
            base_interval: Base interval in hours
            min_factor: Minimum multiplier factor (default from settings)
            max_factor: Maximum multiplier factor (default from settings)
            
        Returns:
            Randomized interval in hours
        """
        min_factor = min_factor or settings.min_random_factor
        max_factor = max_factor or settings.max_random_factor
        
        random_factor = random.uniform(min_factor, max_factor)
        interval = base_interval * random_factor
        
        logger.debug(
            f"Generated uniform random interval",
            base=base_interval,
            factor=random_factor,
            result=interval
        )
        
        return interval
    
    @staticmethod
    def poisson_interval(mean_interval: float) -> float:
        """
        Generate a randomized interval using Poisson distribution.
        
        This creates more natural-looking timing patterns.
        
        Args:
            mean_interval: Mean interval in hours
            
        Returns:
            Randomized interval in hours
        """
        # Scale to make intervals more reasonable
        scale_factor = 1.0
        
        # Generate a random interval from a Poisson process
        # Lambda is rate parameter (events per unit time)
        lambda_param = 1.0 / mean_interval
        
        # Use exponential distribution (time between events in Poisson process)
        interval = np.random.exponential(scale=1.0/lambda_param) * scale_factor
        
        # Ensure interval is reasonable (not too short or too long)
        min_interval = mean_interval * 0.5
        max_interval = mean_interval * 2.0
        
        interval = max(min_interval, min(interval, max_interval))
        
        logger.debug(
            f"Generated Poisson random interval",
            mean=mean_interval,
            result=interval
        )
        
        return interval
    
    @staticmethod
    def normal_interval(mean_interval: float, std_dev: float = None) -> float:
        """
        Generate a randomized interval using normal distribution.
        
        Args:
            mean_interval: Mean interval in hours
            std_dev: Standard deviation in hours (default: 20% of mean)
            
        Returns:
            Randomized interval in hours
        """
        if std_dev is None:
            std_dev = mean_interval * 0.2  # Default 20% std dev
        
        interval = np.random.normal(loc=mean_interval, scale=std_dev)
        
        # Ensure interval is positive and reasonable
        min_interval = mean_interval * 0.5
        max_interval = mean_interval * 1.5
        
        interval = max(min_interval, min(interval, max_interval))
        
        logger.debug(
            f"Generated normal random interval",
            mean=mean_interval,
            std_dev=std_dev,
            result=interval
        )
        
        return interval
    
    @staticmethod
    def get_strategy(strategy_name: str) -> Callable:
        """
        Get a randomization strategy function by name.
        
        Args:
            strategy_name: Name of the strategy ('uniform', 'poisson', 'normal')
            
        Returns:
            Strategy function
        """
        strategies = {
            'uniform': RandomizationStrategy.uniform_interval,
            'poisson': RandomizationStrategy.poisson_interval,
            'normal': RandomizationStrategy.normal_interval
        }
        
        return strategies.get(strategy_name.lower(), RandomizationStrategy.uniform_interval)
    
    @staticmethod
    def calculate_next_interval(
        base_interval: float, 
        strategy: str = 'uniform'
    ) -> timedelta:
        """
        Calculate the next interval using the specified strategy.
        
        Args:
            base_interval: Base interval in hours
            strategy: Name of the randomization strategy to use
            
        Returns:
            A timedelta object representing the randomized interval
        """
        strategy_func = RandomizationStrategy.get_strategy(strategy)
        random_hours = strategy_func(base_interval)
        
        # Convert hours to timedelta
        interval = timedelta(hours=random_hours)
        
        logger.debug(
            f"Next interval calculated",
            base_hours=base_interval,
            strategy=strategy,
            random_hours=random_hours,
            interval_seconds=interval.total_seconds()
        )
        
        return interval
