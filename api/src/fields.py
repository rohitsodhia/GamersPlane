class Password(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    # @classmethod
    # def __modify_schema__(cls, field_schema):
    #     field_schema.update(
    #         pattern='^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$',
    #         # some example postcodes
    #         examples=['SP11 9DG', 'w1j7bu'],
    #     )

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("String required")
        if len(v) < 7:
            raise ValueError("Password too short")
        return v
