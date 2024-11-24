from .cache import TrackedMediaFile
from datetime import datetime
from functools import partial
from peewee import Field, TimestampField
from pprint import pformat
from typing import Any, Dict, Union


class FilterResult(object):
    def __init__(self, result, test_results):
        self.result = bool(result)
        self.test_results = test_results

    def get_test_results_as_str(self):
        output_lines = []
        for test in self.test_results:
            # str() forces datetime to string
            this_line = f"{test['label']} ({str(test['value'])}: {test['result']})"
            output_lines.append(this_line)
        return ", ".join(output_lines)


class FileFilter(object):
    def __init__(self):
        self.conditions = []

    def get_media_file_value(self, media_file: TrackedMediaFile, attr: Field):
        return getattr(media_file, getattr(attr, 'column_name'))
    
    def test_filter(self, media_file) -> FilterResult:
        def evaluate_conditions():
            for label, f_value, f_condition in self.conditions:
                media_file_value = f_value(media_file)
                result = bool(f_condition(media_file))
                yield label, media_file_value, result

        # By default, pass
        main_result = True
        test_results = []
        # Evaluate the conditions and build filter result contents
        for label, media_file_value, result in evaluate_conditions():
            if result is False:
                # OR Logic, first false causes whole filter to fail
                main_result = False
                test_results.append( dict(label=label, result=result, value=media_file_value) )
        return FilterResult(main_result, test_results)
    
    def __str__(self):
        return f"{self.__class__.__name__}"

class FileFilterTime(FileFilter):
    def __init__(self, time_attr: TimestampField, compare_value: datetime):
        self.compare_value = compare_value
        if not isinstance(time_attr, TimestampField):
            raise ValueError(f"Attribute for this filter needs to be type TimestampField, was: {type(time_attr)}")
    
    def process_time(self, val: Union[datetime, float, str]):
        """
        Ensure datetime object, create from timestamp, or parse from string
        """
        if not isinstance(val, datetime):
            if isinstance(val, str):
                for format in [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%Y-%m-%d",
                ]:
                    try:
                        return datetime.strptime(val, format)
                    except ValueError:
                        continue
                raise ValueError(f"Could not parse '{val}' into a datetime object.")
            elif isinstance(val, float):
                try:
                    return datetime.fromtimestamp(val)
                except ValueError:
                    raise ValueError(f"Could not parse {val} as a timestamp into a datetime object.")
            else:
                raise ValueError(f"Could not parse {val} into a datetime object: type {type(val)}")
        else:
            return val


class FileFilterTimeAfter(FileFilterTime):
    def __init__(self, time_attr: TimestampField, compare_value: datetime):
        self.time_attr = time_attr
        self.compare_value = compare_value
        self.conditions = [
            (
                time_attr.column_name,
                lambda media_file: self.process_time(self.get_media_file_value(media_file, time_attr)),
                lambda media_file: self.process_time(self.get_media_file_value(media_file, time_attr)) <= self.process_time(compare_value),
            ),
        ]

class FileFilterTimeBefore(FileFilterTime):
    def __init__(self, time_attr: TimestampField, compare_value: datetime):
        self.time_attr = time_attr
        self.compare_value = compare_value
        self.conditions = [
            (
                time_attr.column_name,
                lambda media_file: self.process_time(self.get_media_file_value(media_file, time_attr)),
                lambda media_file: self.process_time(self.get_media_file_value(media_file, time_attr)) >= self.process_time(compare_value),
            ),
        ]
