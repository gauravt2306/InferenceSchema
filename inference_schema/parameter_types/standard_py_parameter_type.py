# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import base64
import datetime
import pytz
import sys
import json
from dateutil import parser
from .abstract_parameter_type import AbstractParameterType
from ._constants import DATE_FORMAT, DATETIME_FORMAT, TIME_FORMAT, ERR_PYTHON_DATA_NOT_JSON_SERIALIZABLE


class StandardPythonParameterType(AbstractParameterType):
    """
    Class used to specify an expected parameter as a standard Python type.
    """

    def __init__(self, sample_input):
        """
        Construct the StandardPythonParameterType object. Keep items if they are of subtype
        of AbstractParameterType(wrapped item). Support nested dict or list

        - sample_data_type_map: keep wrapped items as a dict
        - sample_data_type_list: keep wrapped items as a list

        :param sample_input:
        :type sample_input:
        """
        super(StandardPythonParameterType, self).__init__(sample_input)
        self.sample_data_type_map = dict()
        self.sample_data_type_list = []
        if self.sample_data_type is dict:
            for k, v in self.sample_input.items():
                if issubclass(type(v), AbstractParameterType):
                    self.sample_data_type_map[k] = v
        elif self.sample_data_type is list or self.sample_data_type is tuple:
            for data in self.sample_input:
                if issubclass(type(data), AbstractParameterType):
                    self.sample_data_type_list.append(data)

    def deserialize_input(self, input_data):
        """
        Convert the provided data into the expected Python object.

        :param input_data:
        :type input_data: varies
        :return:
        :rtype: varies
        """
        if self.sample_data_type is datetime.date:
            input_data = datetime.date.strptime(input_data, DATE_FORMAT)
        elif self.sample_data_type is datetime.datetime:
            input_data = parser.parse(input_data)
        elif self.sample_data_type is datetime.time:
            input_data = parser.parse(input_data).timetz()
        elif self.sample_data_type is bytearray or (sys.version_info[0] == 3 and self.sample_data_type is bytes):
            input_data = base64.b64decode(input_data.encode('utf-8'))
        if not isinstance(input_data, self.sample_data_type):
            raise ValueError("Invalid input data type to parse. Expected: {0} but got {1}".format(
                self.sample_data_type, type(input_data)))

        return input_data

    def input_to_swagger(self):
        """
        Generates a swagger schema for the provided sample type

        :return: The swagger schema object.
        :rtype: dict
        """
        if self.sample_input is None:
            raise ValueError("Python data cannot be None")

        schema = None

        if self.sample_data_type is int:
            schema = {"type": "integer", "format": "int64", "example": self.sample_input}
        elif self.sample_data_type is bytes:
            # Bytes type is not json serializable so will convert to a base 64 string for the sample
            sample = base64.b64encode(self.sample_input).decode('utf-8')
            schema = {"type": "string", "format": "byte", "example": sample}
        elif self.sample_data_type is range:
            schema = self._get_swagger_for_list(self.sample_input, {"type": "integer", "format": "int64"})
        elif self.sample_data_type is str:
            schema = {"type": "string", "example": self.sample_input}
        elif self.sample_data_type is float:
            schema = {"type": "number", "format": "double", "example": self.sample_input}
        elif self.sample_data_type is bool:
            schema = {"type": "boolean", "example": self.sample_input}
        elif self.sample_data_type is datetime.date:
            sample = self.sample_input.strftime(DATE_FORMAT)
            schema = {"type": "string", "format": "date", "example": sample}
        elif self.sample_data_type is datetime.datetime:
            date_time_with_zone = self.sample_input
            if self.sample_input.tzinfo is None:
                # If no timezone data is passed in, consider UTC
                date_time_with_zone = datetime.datetime(self.sample_input.year, self.sample_input.month,
                                                        self.sample_input.day, self.sample_input.hour,
                                                        self.sample_input.minute, self.sample_input.second,
                                                        self.sample_input.microsecond, pytz.utc)
            sample = date_time_with_zone.strftime(DATETIME_FORMAT)
            schema = {"type": "string", "format": "date-time", "example": sample}
        elif self.sample_data_type is datetime.time:
            time_with_zone = self.sample_input
            if self.sample_input.tzinfo is None:
                # If no timezone data is passed in, consider UTC
                time_with_zone = datetime.time(self.sample_input.hour, self.sample_input.minute,
                                               self.sample_input.second, self.sample_input.microsecond, pytz.utc)
            sample = time_with_zone.strftime(TIME_FORMAT)
            schema = {"type": "string", "format": "time", "example": sample}
        elif self.sample_data_type is bytearray:
            # Bytes type is not json serializable so will convert to a base 64 string for the sample
            sample = base64.b64encode(self.sample_input).decode('utf-8')
            schema = {"type": "string", "format": "byte", "example": sample}
        elif self.sample_data_type is list or self.sample_data_type is tuple:
            schema = self._get_swagger_for_list(self.sample_input)
        elif self.sample_data_type is dict:
            schema = self._get_swagger_for_nested_dict(self.sample_input)
        # If we didn't match any type yet, try out best to fit this to an object
        if schema is None:
            schema = {"type": "object", "example": self.sample_input}
        # ensure the schema is JSON serializable
        try:
            json.dumps(schema)
        except TypeError as te:
            raise TypeError(ERR_PYTHON_DATA_NOT_JSON_SERIALIZABLE.format(str(te)))

        return schema

    def _get_swagger_for_list(self, python_data):
        schema = {"type": "array", "items": {"type": "object"}, "example": python_data}
        if not python_data:
            return schema
        item_type = type(python_data[0])
        for data in python_data:
            if type(data) != item_type:
                raise Exception('Error, OpenAPI 2.x does not support mixed type in array.')
        if issubclass(item_type, AbstractParameterType):
            nested_item_swagger = python_data[0].input_to_swagger()
            schema = {"type": "array", "items": nested_item_swagger,
                      "example": [nested_item_swagger['example']]}
        return schema

    def _get_swagger_for_nested_dict(self, python_data):
        nested_items = dict()
        examples = dict()
        required = []
        has_wrapped_items = False
        for k, v in python_data.items():
            required.append(k)
            if issubclass(type(v), AbstractParameterType):
                has_wrapped_items = True
                nested_items_swagger = v.input_to_swagger()
                nested_items[k] = nested_items_swagger
                examples[k] = nested_items_swagger["example"]
            else:
                nested_items[k] = {'type': 'object'}
                examples[k] = v
        if has_wrapped_items:
            schema = {"type": "object", "required": required, "properties": nested_items,
                      "example": examples}
        else:
            schema = {"type": "object", "additionalProperties": {'type': 'object'},
                      "example": python_data}
        return schema
