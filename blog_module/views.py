from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Post, Category, Tag


def post_list(request):
    posts = Post.objects.filter(status="published")
    return render(request, "blog/post_list.html", {"posts": posts})



def post_detail(request, slug):
    post = get_object_or_404(Post.published, slug=slug)
    return render(request, "blog/post_detail.html", {"post": post})


def category_posts(request, slug):
    category = get_object_or_404(Category, slug=slug)
    posts = Post.objects.filter(status="published", category=category)
    return render(request, "blog/post_list.html", {
        "posts": posts,
        "category": category,
    })




def tag_posts(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    posts = Post.published.filter(tags=tag)
    return render(
        request,
        "blog/post_list.html",
        {"tag": tag, "posts": posts},
    )


def post_search(request):
    query = request.GET.get("q", "").strip()
    posts = Post.published.none()

    if query:
        posts = Post.published.filter(
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(body__icontains=query)
            | Q(tags__name__icontains=query)
            | Q(category__name__icontains=query)
        ).distinct()

    return render(
        request,
        "blog/post_list.html",
        {"query": query, "posts": posts},
    )
