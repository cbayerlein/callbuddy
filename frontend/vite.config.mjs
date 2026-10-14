import path from 'node:path';
const state=process.env.CALL_ASSISTANT_STATE||'/var/lib/openclaw/state/projects/call-assistant';
const modules=path.join(state,'work/frontend-deps/node_modules');
export default {root:path.dirname(new URL(import.meta.url).pathname),base:'./',resolve:{alias:[{find:'react-dom',replacement:path.join(modules,'react-dom')},{find:'react',replacement:path.join(modules,'react')},{find:'@mui/material',replacement:path.join(modules,'@mui/material')},{find:'@emotion/react',replacement:path.join(modules,'@emotion/react')},{find:'@emotion/styled',replacement:path.join(modules,'@emotion/styled')},{find:'@fontsource/manrope',replacement:path.join(modules,'@fontsource/manrope')}]},build:{outDir:path.join(state,'packages/web'),emptyOutDir:true,sourcemap:false}};
