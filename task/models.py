from django.db import models
from utils.uuid_generator import generate_custom_id

def generate_task_id():
    return f"task_{generate_custom_id()}"

class Task(models.Model):
    id = models.CharField(primary_key=True, max_length=50, default=generate_task_id, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    assignees = models.ManyToManyField(
        'employee.Employee',
        through='TaskAssignment',
        related_name='tasks'
    )
    due_date = models.DateTimeField(null=True, blank=True)
    file_attach = models.URLField(max_length=500, blank=True, null=True)
    link_attach = models.URLField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class TaskAssignment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey('employee.Employee', on_delete=models.CASCADE, related_name='assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True)
    file_attach = models.URLField(max_length=500, blank=True, null=True)
    link_attach = models.URLField(max_length=500, blank=True, null=True)

    class Meta:
        unique_together = ('task', 'employee')

    def __str__(self):
        return f"{self.employee} assigned to {self.task.title}"
