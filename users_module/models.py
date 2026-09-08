from django.db import models


# courses/models.py
class Province(models.Model):
    name = models.CharField(max_length=100, choices=(
        ('hormozgan', 'هرمزگان'),
        ('kerman', 'کرمان'),
        ('sistan', 'سیستان و بلوچستان')
    ))

    def __str__(self):
        return self.name


class School(models.Model):
    province = models.ForeignKey(Province,models.CASCADE,'schools')
    name = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["province", "name"],
                name="unique_city_per_province",
            )
        ]

    def __str__(self):
        return f"{self.name}"


class Grade(models.Model):
    title = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    school = models.ForeignKey(School, models.CASCADE, 'grades')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class FieldOfStudy(models.Model):
    title = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    grade = models.ForeignKey(Grade, models.CASCADE, 'fields')

    def __str__(self):
        return self.title


class Subject(models.Model):
    title = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    field = models.ForeignKey(FieldOfStudy,models.CASCADE,'subjects')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class Access(models.Model):
    name = models.CharField(max_length=200,choices=(
        ('bank','بانک سوال'),
        ('ticket','تیکت'),
        ('quiz','آزمون'),
        ('course','دوره')
    ))
    subject = models.ForeignKey(Subject,models.CASCADE)