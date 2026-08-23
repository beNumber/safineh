from django.db import models


# courses/models.py

class Grade(models.Model):
    title = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class FieldOfStudy(models.Model):
    title = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class Province(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class City(models.Model):
    province = models.ForeignKey(
        Province,
        on_delete=models.CASCADE,
        related_name="cities",
    )

    name = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["province", "name"],
                name="unique_city_per_province",
            )
        ]

    def __str__(self):
        return f"{self.province.name} - {self.name}"


class Subject(models.Model):
    title = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title
