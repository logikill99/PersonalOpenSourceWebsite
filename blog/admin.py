from django.contrib import admin

from blog.models import Category, Comment, Post


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    pass


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("author", "post", "created_on", "approved")
    list_filter = ("approved",)
    actions = ("approve_comments",)

    @admin.action(description="Approve selected comments")
    def approve_comments(self, request, queryset):
        queryset.update(approved=True)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    pass
