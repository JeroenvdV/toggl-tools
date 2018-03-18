import yaml


class YAMLSettings:

    def __init__(self):

        with open("config.yml", 'r') as config_file:
            self._cfg = yaml.load(config_file)

    def _get_nested(self, data, *args):
        if args and data:
            element = args[0]
            if element:
                value = data.get(element)
                return value if len(args) == 1 else self._get_nested(value, *args[1:])

    def cfg(self, *args):
        return self._get_nested(self._cfg, *args)
