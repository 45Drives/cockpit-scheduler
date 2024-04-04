import os

class ParameterNode:
    def __init__(self, label: str, key: str, children: ParameterNode[]): # type: ignore
        self.label = label
        self.key = key
        self.children = children

class TaskTemplate:
    def __init__(self, name: str, parameterSchema: ParameterNode):
        self.name = name
        self.parameterSchema = parameterSchema
        
