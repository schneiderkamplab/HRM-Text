export const POLICY_VERSION = '2026-09-20';
export const MAX_BYTES = 1024 * 1024;
export const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
type RecordValue = Record<string, unknown>;
function object(value: unknown, keys: string[]): RecordValue {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('invalid');
  const obj = value as RecordValue;
  if (Object.keys(obj).some(k => !keys.includes(k)) || keys.some(k => !(k in obj))) throw Error('invalid');
  return obj;
}
function string(value: unknown, max: number, min = 0): string {
  if (typeof value !== 'string' || value.length < min || value.length > max) throw Error('invalid');
  return value;
}
function integer(value: unknown, min: number, max: number): number {
  if (!Number.isInteger(value) || (value as number) < min || (value as number) > max) throw Error('invalid');
  return value as number;
}
function boolean(value: unknown): boolean {
  if (typeof value !== 'boolean') throw Error('invalid');
  return value;
}
// Construct a canonical allowlisted payload: arbitrary client metadata is not retained.
export function validatePayload(input: unknown) {
  const p = object(input, ['id','policyVersion','rating','pseudonym','comment','consent','chat','metadata']);
  if (!UUID.test(string(p.id,36)) || p.policyVersion !== POLICY_VERSION || !['up','down'].includes(p.rating as string)) throw Error('invalid');
  const consent = object(p.consent, ['improvement','publication','license']);
  const publication = boolean(consent.publication);
  if (consent.improvement !== true || consent.license !== (publication ? 'CC-BY-4.0' : null)) throw Error('invalid');
  const chat = object(p.chat, ['messages','summary']);
  if (!Array.isArray(chat.messages) || chat.messages.length < 1 || chat.messages.length > 1000) throw Error('invalid');
  const messages = chat.messages.map(raw => {
    const m = object(raw, ['role','content']);
    if (!['user','assistant'].includes(m.role as string)) throw Error('invalid');
    return {role: m.role as string, content: string(m.content,100000)};
  });
  let summary = null;
  if (chat.summary !== null) {
    const s = object(chat.summary, ['content','coveredMessages']);
    summary = {content:string(s.content,100000,1),coveredMessages:integer(s.coveredMessages,0,messages.length)};
  }
  const m = object(p.metadata, ['appVersion','platform','modelId','contextTokens','replyTokens','mixedLM']);
  const pseudonym = string(p.pseudonym,80,1);
  if (pseudonym.trim() !== pseudonym || /[\u0000-\u001f\u007f]/.test(pseudonym)) throw Error('invalid');
  return {
    id:p.id as string, policyVersion:POLICY_VERSION, rating:p.rating as 'up'|'down',
    pseudonym, comment:string(p.comment,4000),
    consent:{improvement:true,publication,license:publication ? 'CC-BY-4.0' : null},
    chat:{messages,summary},
    metadata:{appVersion:string(m.appVersion,80,1),platform:string(m.platform,32,1),modelId:string(m.modelId,128),
      contextTokens:integer(m.contextTokens,1,1048576),replyTokens:integer(m.replyTokens,1,1048576),mixedLM:boolean(m.mixedLM)}
  };
}
