from django.contrib import admin

from blog.models import Category, Comment, Post


# Register your models here.
@admin.register(Category)
class CommentAdmin(admin.ModelAdmin):
    pass


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    pass


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    pass