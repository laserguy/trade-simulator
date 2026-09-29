import { useState } from 'react'
import { api, type ProviderStatus, type Settings } from '../api'
import { tradingRuleLines } from '../format'
import { RunModeSection } from './RunModeSection'

const PROVIDER_LABEL: Record<string, string> = { openai: 'OpenAI', anthropic: 'Anthropic' }

interface Props {
  settings: Settings | null
  timezone: string
  currency: string
  onChange: (settings: Settings) => void
  onError: (message: string) => void
}

export function SettingsView({ settings, timezone, currency, onChange, onError }: Props) {
  if (!settings) return <p className="muted">Loading settings…</p>

  const save = async (action: Promise<Settings>) => {
    try {
      onChange(await action)
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Saving failed')
    }
  }
  const hasOpenAi = settings.providers.some((p) => p.provider === 'openai' && p.has_key)

  return (
    <>
      <div className="card">
        <h2>API keys</h2>
        <p className="muted" style={{ marginTop: 0, fontSize: 14 }}>
          Keys are stored only on this computer and sent only to their provider. Models appear below for each provider with a key.
        </p>
        {settings.providers.map((provider) => (
          <KeyRow
            key={provider.provider}
            provider={provider}
            onSave={(key) => save(api.saveKey(provider.provider, key))}
          />
        ))}
      </div>

      <div className="card">
        <div className="card-head">
          <h2>Model for all agents</h2>
          <span className="muted" style={{ fontSize: 13 }}>Prices as of {settings.catalogue_as_of}</span>
        </div>
        {settings.models.length === 0 ? (
          <div className="empty">Add an OpenAI or Anthropic API key to choose a model.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th></th>
                  <th>Model</th>
                  <th>Provider</th>
                  <th className="r">Input $/1M tokens</th>
                  <th className="r">Output $/1M tokens</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {settings.models.map((m) => {
                  const selected = m.model_id === settings.selected_model_id
                  return (
                    <tr
                      key={m.model_id}
                      className={`model-row ${selected ? 'selected' : ''}`}
                      onClick={() => !selected && save(api.selectModel(m.model_id))}
                    >
                      <td>
                        <input type="radio" name="model" checked={selected} readOnly aria-label={m.label} />
                      </td>
                      <td><strong>{m.label}</strong> <span className="muted" style={{ fontSize: 12 }}>{m.model_id}</span></td>
                      <td className="provider-tag">{PROVIDER_LABEL[m.provider] ?? m.provider}</td>
                      <td className="r num">${m.input_usd_per_million}</td>
                      <td className="r num">${m.output_usd_per_million}</td>
                      <td className="muted">{m.note}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted" style={{ fontSize: 13, marginBottom: 0 }}>
          The choice applies from the next run. {hasOpenAi
            ? 'Runs are traced in your OpenAI dashboard, whichever model you pick.'
            : 'Without an OpenAI key, runs are not traced; the decision log still records every decision.'}
        </p>
      </div>

      <RunModeSection settings={settings} timezone={timezone} onSelect={(mode) => save(api.setRunMode(mode))} />

      <div className="card">
        <h2>Trading rules</h2>
        <p className="muted" style={{ marginTop: 0, fontSize: 14 }}>
          Checked by the app on every order the agent proposes; orders that break them are rejected and logged.
        </p>
        <ul className="rules">
          {tradingRuleLines(settings.trading_rules, currency).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </div>
    </>
  )
}

function KeyRow({ provider, onSave }: { provider: ProviderStatus; onSave: (key: string | null) => void }) {
  const [draft, setDraft] = useState('')
  const label = PROVIDER_LABEL[provider.provider] ?? provider.provider
  return (
    <div className="form-row">
      <span className="name">{label}</span>
      <span className="muted" style={{ minWidth: 150, fontSize: 14 }}>
        {provider.has_key ? `Key ${provider.masked_key}` : 'No key'}
      </span>
      <input
        type="password"
        placeholder={provider.has_key ? 'Replace key…' : `Paste ${label} API key`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        autoComplete="off"
      />
      <button
        className="btn small primary"
        disabled={!draft.trim()}
        onClick={() => {
          onSave(draft.trim())
          setDraft('')
        }}
      >
        Save
      </button>
      {provider.has_key && (
        <button className="btn small" onClick={() => onSave(null)}>
          Remove
        </button>
      )}
    </div>
  )
}
