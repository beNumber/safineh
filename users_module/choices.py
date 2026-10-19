from django import forms
from django.db.models import Min, Subquery
from django.forms.models import ModelChoiceIterator


def title_representatives(queryset):
    identifiers = queryset.order_by().values("title").annotate(identifier=Min("pk")).values("identifier")
    return queryset.filter(pk__in=Subquery(identifiers)).order_by("title", "pk")


class UniqueTitleIterator(ModelChoiceIterator):
    def __iter__(self):
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        for item in title_representatives(self.queryset):
            yield self.choice(item)

    def __len__(self):
        return title_representatives(self.queryset).count() + (self.field.empty_label is not None)


class UniqueTitleChoiceField(forms.ModelChoiceField):
    iterator = UniqueTitleIterator

    def prepare_value(self, value):
        if hasattr(value, "_meta"):
            return super().prepare_value(value)
        identifier = super().prepare_value(value)
        if identifier in self.empty_values:
            return identifier
        try:
            title = self.queryset.filter(pk=identifier).values_list("title", flat=True).first()
        except (TypeError, ValueError):
            return identifier
        if title is None:
            return identifier
        return self.queryset.filter(title=title).order_by("pk").values_list("pk", flat=True).first()


class UniqueTitleMultipleChoiceField(forms.ModelMultipleChoiceField):
    iterator = UniqueTitleIterator

    def prepare_value(self, value):
        prepared = super().prepare_value(value)
        if prepared is None or isinstance(prepared, (str, bytes, int)):
            return prepared
        identifiers = list(prepared)
        try:
            titles = self.queryset.filter(pk__in=identifiers).values_list("title", flat=True)
            return list(title_representatives(self.queryset).filter(title__in=titles).values_list("pk", flat=True))
        except (TypeError, ValueError):
            return identifiers

    def clean(self, value):
        if isinstance(value, (list, tuple)) and value:
            self._check_values(value)
        selected = super().clean(value)
        return self.queryset.filter(title__in=selected.values("title"))
