from odoo import models, fields, api, _

class AccountMove(models.Model):
    _inherit = 'account.move'

    # Header tags (invoice & payments)
    x_building_id = fields.Many2one('estate.building', string='البناية')
    x_unit_id = fields.Many2one('estate.building.unit', string='الوحدة/الشقة', domain="[('building_id','=',x_building_id)]")
    x_floor = fields.Integer(string='الطابق')
    x_unit_number = fields.Char(string='الشقة')
    x_owner_id = fields.Many2one('res.partner', string='المالك / Owner', domain=[('is_property_owner', '=', True)])

    # Convenience for reporting
    x_tenant_partner_id = fields.Many2one('res.partner', string='المستأجر', compute='_compute_tenant', store=False)

    @api.depends('partner_id')
    def _compute_tenant(self):
        for mv in self:
            mv.x_tenant_partner_id = mv.partner_id

    
    def _sync_prepayment_amounts(self):
        """Push the invoice total/currency into linked rent.prepayment rows."""
        preps = self.env['rent.prepayment'].search([('move_id', 'in', self.ids)])
        for prep in preps:
            new_amt = abs(prep.move_id.amount_total)
            new_cur = prep.move_id.currency_id.id
            # write without bouncing back (one-way sync: invoice -> prepayment)
            prep.with_context(from_invoice_sync=True).write({
                'amount': new_amt,
                'currency_id': new_cur,
            })

    def write(self, vals):
        res = super().write(vals)
        # Trigger when invoice content likely changed totals
        keys = {'invoice_line_ids', 'currency_id', 'line_ids', 'move_type'}
        if not self.env.context.get('from_prepayment_sync') and keys & set(vals.keys()):
            self._sync_prepayment_amounts()
        return res

    def action_post(self):
        res = super().action_post()
        if not self.env.context.get('from_prepayment_sync'):
            self._sync_prepayment_amounts()
        return res

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Propagate to GL lines (stored, groupable)
    x_building_id = fields.Many2one('estate.building', related='move_id.x_building_id', store=True)
    x_unit_id = fields.Many2one('estate.building.unit', related='move_id.x_unit_id', store=True)
    x_floor = fields.Integer(related='move_id.x_floor', store=True)
    x_unit_number = fields.Char(related='move_id.x_unit_number', store=True)
    x_tenant_partner_id = fields.Many2one('res.partner', related='move_id.partner_id', store=True)
    x_owner_id = fields.Many2one('res.partner', related='move_id.x_owner_id', store=True)