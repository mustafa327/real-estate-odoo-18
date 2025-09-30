from odoo import models, fields, api, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_building_id = fields.Many2one('estate.building', string='البناية')
    x_unit_id = fields.Many2one('estate.building.unit', string='الوحدة/الشقة', domain="[('building_id','=',x_building_id)]")
    x_floor = fields.Integer(string='الطابق')
    x_unit_number = fields.Char(string='الشقة')

    @api.onchange('partner_id')
    def _onchange_partner_building(self):
        for so in self:
            if so.partner_id:
                so.x_building_id = so.partner_id.x_building_id
                so.x_unit_id = so.partner_id.x_unit_id
                so.x_floor = so.partner_id.x_floor
                so.x_unit_number = so.partner_id.x_unit_number

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        vals.update({
            'x_building_id': self.x_building_id.id,
            'x_unit_id': self.x_unit_id.id,
            'x_floor': self.x_floor,
            'x_unit_number': self.x_unit_number,
        })
        return vals