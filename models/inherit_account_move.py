from odoo import models, fields, api, _

class AccountMove(models.Model):
    _inherit = 'account.move'

    # Header tags (invoice & payments)
    x_building_id = fields.Many2one('estate.building', string='البناية')
    x_unit_id = fields.Many2one('estate.building.unit', string='الوحدة/الشقة', domain="[('building_id','=',x_building_id)]")
    x_floor = fields.Integer(string='الطابق')
    x_unit_number = fields.Char(string='الشقة')

    # Convenience for reporting
    x_tenant_partner_id = fields.Many2one('res.partner', string='المستأجر', compute='_compute_tenant', store=False)

    @api.depends('partner_id')
    def _compute_tenant(self):
        for mv in self:
            mv.x_tenant_partner_id = mv.partner_id

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Propagate to GL lines (stored, groupable)
    x_building_id = fields.Many2one('estate.building', related='move_id.x_building_id', store=True)
    x_unit_id = fields.Many2one('estate.building.unit', related='move_id.x_unit_id', store=True)
    x_floor = fields.Integer(related='move_id.x_floor', store=True)
    x_unit_number = fields.Char(related='move_id.x_unit_number', store=True)
    x_tenant_partner_id = fields.Many2one('res.partner', related='move_id.partner_id', store=True)