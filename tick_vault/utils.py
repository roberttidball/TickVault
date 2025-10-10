from datetime import datetime, timedelta


def generate_hourly_datetimes(start: datetime, end: datetime) -> list[datetime]:
    """
    Generate all hourly datetime objects within a given range.

    Creates a list of datetime objects, one for each hour from start to end,
    rounded down to the hour. The end hour is excluded to avoid including
    incomplete data (e.g., when called with datetime.now()).

    Args:
        start: The start datetime of the range (will be rounded down to the hour)
        end: The end datetime of the range (will be rounded down to the hour, excluded)

    Returns:
        list[datetime]: A list of datetime objects, one for each complete hour
            in the range [start_hour, end_hour). Returns empty list if the
            rounded start and end are the same hour.

    Raises:
        TypeError: If start or end are not datetime objects
        ValueError: If end is before or equal to start

    Examples:
        >>> start = datetime(2024, 3, 2, 12, 30)
        >>> end = datetime(2024, 3, 2, 15, 45)
        >>> generate_hourly_datetimes(start, end)
        [datetime(2024, 3, 2, 12, 0),
         datetime(2024, 3, 2, 13, 0),
         datetime(2024, 3, 2, 14, 0),
         datetime(2024, 3, 2, 15, 0)]

        >>> # Same hour after rounding
        >>> start = datetime(2024, 3, 2, 12, 15)
        >>> end = datetime(2024, 3, 2, 12, 45)
        >>> generate_hourly_datetimes(start, end)
        []
    """
    if not isinstance(start, datetime):
        raise TypeError(
            f"Start must be a datetime object, got {type(start).__name__}"
        )
    
    if not isinstance(end, datetime):
        raise TypeError(
            f"End must be a datetime object, got {type(end).__name__}"
        )
    
    if end <= start:
        raise ValueError(
            f"End datetime must be after start datetime. Got start={start}, end={end}"
        )

    # Round down to the hour
    current = start.replace(minute=0, second=0, microsecond=0)
    end_hour = end.replace(minute=0, second=0, microsecond=0)

    datetimes: list[datetime] = []
    while current < end_hour:
        datetimes.append(current)
        current += timedelta(hours=1)
    
    return datetimes