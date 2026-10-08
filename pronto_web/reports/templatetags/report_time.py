from django import template

from pronto_report.renderers.display_time import oslo_time


register = template.Library()
register.filter('oslo_time', oslo_time)
