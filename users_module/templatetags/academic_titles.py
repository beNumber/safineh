from django import template


register = template.Library()


@register.filter
def unique_titles(items):
    titles = set()
    result = []
    for item in items:
        if item.title not in titles:
            titles.add(item.title)
            result.append(item)
    return result
