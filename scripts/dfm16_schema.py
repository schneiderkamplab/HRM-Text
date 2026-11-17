"""Validate declared dialects; normalize legacy bounds in undeclared schemas."""
import copy
import jsonschema


def checked_schema(schema):
    schema = copy.deepcopy(schema)
    def repair(node):
        if not isinstance(node, dict):
            return
        for exclusive, bound in (('exclusiveMinimum', 'minimum'), ('exclusiveMaximum', 'maximum')):
            if isinstance(node.get(exclusive), bool):
                enabled = node.pop(exclusive)
                if enabled:
                    if bound not in node:
                        raise ValueError('Legacy exclusive bound without '+bound)
                    node[exclusive] = node.pop(bound)
        properties = node.get('properties', {})
        for name, child in properties.items():
            if isinstance(child, dict) and isinstance(child.get('required'), bool):
                if child.pop('required'):
                    if not isinstance(node.setdefault('required', []), list):
                        raise ValueError('Invalid parent required list')
                    if name not in node['required']:
                        node['required'].append(name)
        # Visit schema-valued keywords, never literal examples, const, or defaults.
        for key in ('properties', 'patternProperties', '$defs', 'definitions', 'dependentSchemas'):
            value = node.get(key)
            if isinstance(value, dict):
                for child in value.values():
                    repair(child)
        for key in ('items', 'additionalProperties', 'contains', 'propertyNames', 'not', 'if', 'then', 'else',
                    'unevaluatedProperties', 'unevaluatedItems'):
            repair(node.get(key))
        for key in ('allOf', 'anyOf', 'oneOf', 'prefixItems'):
            for child in node.get(key, []):
                repair(child)
    if isinstance(schema, dict) and '$schema' not in schema:
        repair(schema)
        schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
    validator = jsonschema.validators.validator_for(schema)
    validator.check_schema(schema)
    return schema
