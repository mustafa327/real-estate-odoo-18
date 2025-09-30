# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class EstateBuilding(models.Model):
    _name = 'estate.building'
    _description = 'Building'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='اسم البناية / Building', required=True, tracking=True)
    code = fields.Char(string='كود', tracking=True)
    street = fields.Char(string='العنوان')
    city = fields.Char()
    state_id = fields.Many2one('res.country.state', string='المحافظة')
    country_id = fields.Many2one('res.country', string='الدولة')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

    unit_ids = fields.One2many('estate.building.unit', 'building_id', string='الشقق/الوحدات')
    # requires inherit on hr.department defining x_building_id
    department_ids = fields.One2many('hr.department', 'x_building_id', string='الأقسام داخل البناية')

    currency_id = fields.Many2one(related='company_id.currency_id', store=True, readonly=True)

    revenue_monthly_expected = fields.Monetary(string='إيراد شهري متوقع',
                                               compute='_compute_expected_revenue')
    revenue_yearly_expected = fields.Monetary(string='إيراد سنوي متوقع',
                                              compute='_compute_expected_revenue')

    contract_count = fields.Integer(compute='_compute_contract_count')
    unit_count = fields.Integer(compute='_compute_unit_count')

    @api.depends(
        'unit_ids.contract_ids.state',
        'unit_ids.contract_ids.amount',
        'unit_ids.contract_ids.recurrence',
        'unit_ids.contract_ids.start_date',
        'unit_ids.contract_ids.end_date',
    )
    def _compute_expected_revenue(self):
        """Compute expected monthly/yearly revenue from ACTIVE contracts only.
        Always assign values for every record (even if zero)."""
        today = fields.Date.context_today(self)
        for b in self:
            monthly = 0.0
            yearly = 0.0
            # handle no units gracefully
            for u in b.unit_ids:
                active_contracts = u.contract_ids.filtered(
                    lambda c: c.state == 'active'
                    and (not c.start_date or c.start_date <= today)
                    and (not c.end_date or c.end_date >= today)
                )
                for c in active_contracts:
                    if c.recurrence == 'month':
                        monthly += c.amount
                        yearly += c.amount * 12.0
                    else:
                        yearly += c.amount
                        monthly += c.amount / 12.0
            # ✅ must ALWAYS assign
            b.revenue_monthly_expected = monthly
            b.revenue_yearly_expected = yearly

    def _compute_contract_count(self):
        for b in self:
            b.contract_count = self.env['rent.contract'].search_count([('building_id', '=', b.id)])

    def _compute_unit_count(self):
        for b in self:
            b.unit_count = len(b.unit_ids)

    # Buttons shown in the Building form header
    def action_view_contracts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rent Contracts'),
            'res_model': 'rent.contract',
            'view_mode': 'list,form,graph,pivot',  # v18 uses "list" not "tree"
            'domain': [('building_id', '=', self.id)],
            'context': {'default_building_id': self.id},
        }

    def action_view_units(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Units'),
            'res_model': 'estate.building.unit',
            'view_mode': 'list,form,kanban',  # v18
            'domain': [('building_id', '=', self.id)],
            'context': {'default_building_id': self.id},
        }


# keep the department link in its own inherited model (or here if you prefer)
class HrDepartment(models.Model):
    _inherit = 'hr.department'
    x_building_id = fields.Many2one('estate.building', string='البناية', ondelete='set null')
