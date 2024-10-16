from django.shortcuts import render
from django.http import HttpResponseRedirect

from blog.forms import CommentForm
from blog.models import Comment, Post


# Create your views here.
def blog_detail(request, pk: int):
    post = Post.objects.get(pk=pk)
    form = CommentForm()
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = Comment(
                author=form.cleaned_data["author"],
                body=form.cleaned_data["body"],
                post=post,
            )
            comment.save()
            return HttpResponseRedirect(request.path_info)
    comments = Comment.objects.filter(post=post)
    context = {"post": post, "comments": comments, "form": form}

    return render(request, "post_detail.html", context)
