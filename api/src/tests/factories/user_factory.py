import math
import random
from datetime import datetime

import factory
from mimesis import Generic
from mimesis_factory import MimesisField
from users.models import User

random_seed = math.floor(random.random() * 100000)
mimesis = Generic(seed=random_seed)


class UserFactory(factory.Factory):
    class Meta(object):
        model = User

    username = MimesisField("username", template="l_d")
    password = "test1234"
    email = factory.LazyAttribute(
        lambda instance: "{0}@test.com".format(instance.username)
    )
    joinDate = datetime.now()
    activatedOn = datetime.now()
