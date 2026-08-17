from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render

from PersonalHomePage.ratelimit import is_rate_limited
from blog.forms import CommentForm
from blog.models import Comment, Post


def blog_detail(request, pk: int):
    post = get_object_or_404(Post, pk=pk)
    form = CommentForm()
    if request.method == "POST":
        if request.POST.get("website"):
            return HttpResponseRedirect(request.path_info)
        form = CommentForm(request.POST)
        if form.is_valid():
            if is_rate_limited(request, key_prefix="comment", record=True):
                messages.error(request, "Too many comments. Wait a minute and try again.")
            else:
                Comment.objects.create(
                    author=form.cleaned_data["author"],
                    body=form.cleaned_data["body"],
                    post=post,
                )
                return HttpResponseRedirect(request.path_info)
    comments = Comment.objects.filter(post=post)
    context = {"post": post, "comments": comments, "form": form}
    return render(request, "post_detail.html", context)


def blog_index(request):
    posts = Post.objects.all().order_by("-created_on")
    context = {"posts": posts}
    return render(request, "blog_index.html", context)
