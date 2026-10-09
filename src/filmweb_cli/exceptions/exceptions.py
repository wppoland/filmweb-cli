class FilmwebError(Exception):
    pass


class ContentNotFoundError(FilmwebError):
    pass


class InvalidContentError(FilmwebError):
    pass


class InvalidIdTypeError(FilmwebError):
    pass


class InvalidIdPrefixError(FilmwebError):
    pass


class AuthRequiredError(FilmwebError):
    pass
