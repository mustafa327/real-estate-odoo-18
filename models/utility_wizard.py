# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class RentUtilityWizard(models.TransientModel):
    _name = 'rent.utility.wizard'
    _description = 'Add Utilities to Contract Invoice'

    contract_id = fields.Many2one('rent.contract', required=True)
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    line_ids = fields.One2many('rent.utility.wizard.line', 'wizard_id', required=True)

    def action_add_to_invoice(self):
        self.ensure_one()
        contract = self.contract_id
        if not contract:
            raise UserError(_("No contract selected."))

        partner = contract._get_tenant_partner() 

        Move = self.env['account.move']
        move = Move.search([
            ('move_type', '=', 'out_invoice'),
            ('partner_id', '=', partner.id),
            ('state', '=', 'draft'),
            ('contract_id', '=', contract.id),
        ], limit=1)

        if not move:
            move = Move.create({
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'invoice_origin': contract.name,
                'invoice_date': fields.Date.context_today(self),
                'company_id': contract.company_id.id,
                'currency_id': contract.currency_id.id,
                'contract_id': contract.id,
                'x_building_id': contract.building_id.id,
                'x_unit_id': contract.unit_id.id,
                'x_floor': contract.unit_id.floor,
                'x_unit_number': contract.unit_id.unit_number,
                'x_owner_id': contract.owner_id.id,
            })

        for wl in self.line_ids:
            if wl.amount <= 0:
                raise UserError(_("Amount for line '%s' must be > 0.") % (wl.type_id.name,))
            product = wl.type_id.product_id
            aml_vals = {
                'move_id': move.id,
                'product_id': product.id,
                'name': "%s (%s → %s)" % (
                    wl.type_id.name,
                    self.period_start or '',
                    self.period_end or '',
                ),
                'quantity': (wl.units if wl.type_id.pricing == 'meter' else 1.0) or 1.0,
                'price_unit': (wl.unit_rate if wl.type_id.pricing == 'meter' else wl.amount),
            }
            line = self.env['account.move.line'].with_context(check_move_validity=False).create(aml_vals)

            self.env['rent.utility.expense'].create({
                'name': line.name,
                'contract_id': contract.id,
                'type_id': wl.type_id.id,
                'period_start': self.period_start,
                'period_end': self.period_end,
                'reading_start': wl.reading_start,
                'reading_end': wl.reading_end,
                'units': wl.units,
                'unit_rate': wl.unit_rate,
                'amount': wl.amount if wl.type_id.pricing == 'fixed' else (wl.units * wl.unit_rate),
                'currency_id': move.currency_id.id,
                'invoice_id': move.id,
                'move_line_id': line.id,
                'notes': wl.notes,
            })

        # recompute totals/taxes
        if hasattr(move, '_onchange_invoice_line_ids'):
            move._onchange_invoice_line_ids()
        if hasattr(move, '_recompute_payment_terms_lines'):
            move._recompute_payment_terms_lines()

        contract._apply_prepayment_to_invoice(move)
        if hasattr(move, '_onchange_invoice_line_ids'):
            move._onchange_invoice_line_ids()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }


class RentUtilityWizardLine(models.TransientModel):
    _name = 'rent.utility.wizard.line'
    _description = 'Add Utilities to Contract Invoice - Line'

    wizard_id = fields.Many2one('rent.utility.wizard', required=True, ondelete='cascade')
    type_id = fields.Many2one('rent.utility.type', required=True)
    reading_start = fields.Float()
    reading_end = fields.Float()
    units = fields.Float(compute='_compute_units', store=True)
    unit_rate = fields.Float()
    amount = fields.Monetary(currency_field='currency_id', required=True)
    currency_id = fields.Many2one(
        'res.currency', default=lambda s: s.env.company.currency_id.id, required=True
    )

    type_pricing = fields.Selection(related='type_id.pricing', store=False, readonly=True)

    notes = fields.Char()

    @api.onchange('type_id')
    def _onchange_type(self):
        if self.type_id:
            self.unit_rate = self.type_id.unit_rate
            if self.type_id.pricing == 'fixed':
                self.amount = self.type_id.unit_rate

    @api.depends('reading_start', 'reading_end', 'type_id.pricing')
    def _compute_units(self):
        for rec in self:
            if rec.type_id and rec.type_id.pricing == 'meter':
                rec.units = max((rec.reading_end or 0.0) - (rec.reading_start or 0.0), 0.0)
            else:
                rec.units = 1.0

    @api.onchange('units', 'unit_rate', 'type_id')
    def _onchange_amount(self):
        for rec in self:
            if rec.type_id and rec.type_id.pricing == 'meter':
                rec.amount = (rec.units or 0.0) * (rec.unit_rate or 0.0)
