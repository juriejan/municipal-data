from django.db import models
from django.db.models import Sum
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex

from scorecard.models import Geography


class FinancialYear(models.Model):
    budget_year = models.CharField(max_length=10)

    def __str__(self):
        return self.budget_year


class BudgetPhase(models.Model):
    code = models.CharField(max_length=10, null=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class ProjectQuerySet(models.QuerySet):
    def total_value(self, budget_year, budget_phase):
        qs = self
        res = Expenditure.objects.filter(
            financial_year__budget_year=budget_year,
            budget_phase__name=budget_phase,
            project__in=qs,
        ).aggregate(total=Sum("amount"))

        return res["total"]


class ProjectManager(models.Manager):
    def get_queryset(self):
        return ProjectQuerySet(self.model, using=self._db)
        # return ProjectQuerySet(self.model, using=self._db).prefetch_related(
        #     "expenditure", "expenditure__financial_year", "expenditure__budget_phase"
        # )


class Project(models.Model):
    geography = models.ForeignKey(
        Geography, on_delete=models.CASCADE, null=False, related_name="geographies"
    )
    function = models.CharField(max_length=255, blank=True)
    project_description = models.CharField(max_length=255, blank=True)
    project_number = models.CharField(max_length=30, blank=True)
    project_type = models.CharField(max_length=20, blank=True)
    mtsf_service_outcome = models.CharField(max_length=100, blank=True)
    iudf = models.CharField(max_length=255, blank=True)
    own_strategic_objectives = models.CharField(max_length=255, blank=True)
    asset_class = models.CharField(max_length=255, blank=True)
    asset_subclass = models.CharField(max_length=255, blank=True)
    ward_location = models.CharField(max_length=255, blank=True)
    longitude = models.FloatField(null=True)
    latitude = models.FloatField(null=True)

    content_search = SearchVectorField(null=True)

    objects = ProjectManager()

    class Meta:
        indexes = [GinIndex(fields=["content_search"])]

    def __str__(self):
        return "%s - %s" % (self.geography, self.project_description)


class Expenditure(models.Model):
    project = models.ForeignKey(
        Project, null=False, on_delete=models.CASCADE, related_name="expenditure"
    )
    budget_phase = models.ForeignKey(BudgetPhase, null=False, on_delete=models.CASCADE)
    financial_year = models.ForeignKey(
        FinancialYear, null=False, on_delete=models.CASCADE
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)

    def __str__(self):
        return "%s - %s (%s)" % (self.project, self.budget_phase, self.financial_year)
