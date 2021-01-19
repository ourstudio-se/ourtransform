class FakeLogger(object):

    def __init__(self):
        self.debugs = []
        self.infos = []
        self.warnings = []
        self.errors = []
        self.criticals = []

    def debug(self, msg, *args, **kwargs):
        print(f"[FAKE LOGGER][DEBUG] {msg}") 
        self.debugs.append(msg)
        
    def info(self, msg, *args, **kwargs):
        print(f"[FAKE LOGGER][INFO] {msg}")
        self.infos.append(msg)
    
    def warning(self, msg, *args, **kwargs):
        print(f"[FAKE LOGGER][WARNING] {msg}") 
        self.warnings.append(msg)
        
    def error(self, msg, *args, **kwargs):
        print(f"[FAKE LOGGER][ERROR] {msg}") 
        self.errors.append(msg)

    def critical(self, msg, *args, **kwargs):
        print(f"[FAKE LOGGER][CRITIAL] {msg}") 
        self.criticals.append(msg)
