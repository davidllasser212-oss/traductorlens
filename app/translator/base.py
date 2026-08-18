from abc import ABC, abstractmethod


class Translator(ABC):
    @abstractmethod
    def translate(self, text, src="auto", dst="es"):
        raise NotImplementedError