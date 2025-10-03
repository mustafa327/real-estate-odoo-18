from odoo import models, fields, api, _

class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_building_id = fields.Many2one('estate.building', string='اسم البناية')
    x_unit_id = fields.Many2one('estate.building.unit', string='رقم الشقة/الوحدة', domain="[('building_id','=',x_building_id)]")
    x_floor = fields.Integer(string='رقم الطابق', related='x_unit_id.floor', store=True)
    x_unit_number = fields.Char(string='رقم الشقة', related='x_unit_id.unit_number', store=True)
    is_property_owner = fields.Boolean(string="Property Owner / مالك العقار")