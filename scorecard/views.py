from django.shortcuts import redirect
from django.views.generic.base import TemplateView
from django.http import Http404
from django.urls import reverse
from wkhtmltopdf.views import PDFResponse
from wkhtmltopdf.utils import wkhtmltopdf

from scorecard.profiles import get_profile
from scorecard.models import Geography, LocationNotFound
from infrastructure.models import Project
from household.models import HouseholdServiceTotal, HouseholdBillTotal
from household.chart import stack_chart, chart_data, percent_increase, yearly_percent


from . import models
from . import serializers
from rest_framework import viewsets


class GeographyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Geography.objects.all()
    serializer_class = serializers.GeographySerializer


class LocateView(TemplateView):
    template_name = "locate.html"

    def get(self, request, *args, **kwargs):
        self.lat = self.request.GET.get("lat", None)
        self.lon = self.request.GET.get("lon", None)
        self.nope = False

        if self.lat and self.lon:
            place = None
            places = Geography.get_locations_from_coords(
                latitude=self.lat, longitude=self.lon
            )

            if places:
                place = places[0]

                # if multiple, prefer the metro/local municipality if available
                if len(places) > 1:
                    places = [p for p in places if p.geo_level == "municipality"]
                    if places:
                        place = places[0]

                return redirect(
                    reverse("geography_detail", kwargs={"geography_id": place.geoid})
                )
            self.nope = True

        return super(LocateView, self).get(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        return {"nope": self.nope, "lat": self.lat, "lon": self.lon}


class GeographyDetailView(TemplateView):
    template_name = "profile/profile_detail.html"

    def dispatch(self, *args, **kwargs):
        self.geo_id = self.kwargs.get("geography_id", None)

        try:
            self.geo_level, self.geo_code = self.geo_id.split("-", 1)
            self.geo = Geography.find(self.geo_code, self.geo_level)
        except (ValueError, LocationNotFound):
            raise Http404

        # check slug
        if kwargs.get("slug") or self.geo.slug:
            if kwargs["slug"] != self.geo.slug:
                kwargs["slug"] = self.geo.slug
                url = "/profiles/%s-%s-%s/" % (
                    self.geo_level,
                    self.geo_code,
                    self.geo.slug,
                )
                return redirect(url, permanent=True)

        return super(GeographyDetailView, self).dispatch(*args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        page_context = {}

        profile = get_profile(self.geo)
        page_context.update(profile)

        profile["geography"] = self.geo.as_dict()
        page_context["profile_data"] = profile
        page_context["geography"] = self.geo

        profile["demarcation"]["disestablished_to_geos"] = [
            Geography.objects.filter(geo_code=code).first().as_dict()
            for code in profile["demarcation"].get("disestablished_to", [])
        ]

        profile["demarcation"]["established_from_geos"] = [
            Geography.objects.filter(geo_code=code).first().as_dict()
            for code in profile["demarcation"].get("established_from", [])
        ]

        for date in profile["demarcation"]["land_gained"]:
            for change in date["changes"]:
                change["geo"] = (
                    Geography.objects.filter(geo_code=change["demarcation_code"])
                    .first()
                    .as_dict()
                )
        for date in profile["demarcation"]["land_lost"]:
            for change in date["changes"]:
                change["geo"] = (
                    Geography.objects.filter(geo_code=change["demarcation_code"])
                    .first()
                    .as_dict()
                )
        infrastructure = (
            Project.objects.prefetch_related(
                "geography",
                "expenditure__budget_phase",
                "expenditure__financial_year",
                "expenditure",
            )
            .filter(
                geography__geo_code=self.geo_code,
                expenditure__budget_phase__name="Budget year",
                expenditure__financial_year__budget_year="2019/2020",
            )
            .order_by("-expenditure__amount")[:5]
            .values("project_description", "expenditure__amount", "id")
        )
        page_context["infrastructure"] = infrastructure

        households = HouseholdBillTotal.summary.bill_totals(self.geo_code)
        page_context["household_percent"] = percent_increase(households)
        page_context["yearly_percent"] = yearly_percent(households)

        chart = chart_data(households)

        page_context["household_chart_overall"] = chart

        service_middle = (
            HouseholdServiceTotal.summary.active(self.geo_code)
            .middle()
            .order_by("financial_year__budget_year")
        )
        service_affordable = (
            HouseholdServiceTotal.summary.active(self.geo_code)
            .affordable()
            .order_by("financial_year__budget_year")
        )
        service_indigent = (
            HouseholdServiceTotal.summary.active(self.geo_code)
            .indigent()
            .order_by("financial_year__budget_year")
        )

        chart_middle = stack_chart(service_middle, households)
        chart_affordable = stack_chart(service_affordable, households)
        chart_indigent = stack_chart(service_indigent, households)

        page_context["household_chart_middle"] = chart_middle
        page_context["household_chart_affordable"] = chart_affordable
        page_context["household_chart_indigent"] = chart_indigent
        # is this a head-to-head view?
        if "head2head" in self.request.GET:
            page_context["head2head"] = "head2head"

        return page_context


class GeographyPDFView(GeographyDetailView):
    def get(self, request, *args, **kwargs):
        # render as pdf
        url = "/profiles/%s-%s-%s?print=1" % (
            self.geo_level,
            self.geo_code,
            self.geo.slug,
        )
        url = request.build_absolute_uri(url)
        pdf = wkhtmltopdf(url, zoom=0.7)
        filename = "%s-%s-%s.pdf" % (self.geo_level, self.geo_code, self.geo.slug)

        return PDFResponse(pdf, filename=filename)


class GeographyCompareView(TemplateView):
    template_name = "profile/head2head.html"

    def get_context_data(self, geo_id1, geo_id2):
        page_context = {"geo_id1": geo_id1, "geo_id2": geo_id2}

        try:
            level, code = geo_id1.split("-", 1)
            page_context["geo1"] = Geography.find(code, level)

            level, code = geo_id2.split("-", 1)
            page_context["geo2"] = Geography.find(code, level)
        except (ValueError, LocationNotFound):
            raise Http404

        return page_context


class SitemapView(TemplateView):
    template_name = "sitemap.txt"
    content_type = "text/plain"

    def get_context_data(self):
        return {"geos": Geography.objects.all()}
