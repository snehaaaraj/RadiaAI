type ViteEnvOptions = {
    frontendRoot?: string;
    workspaceRoot?: string;
    env?: NodeJS.ProcessEnv;
};
export declare function loadRadiaViteEnv(mode: string, options?: ViteEnvOptions): {
    [x: string]: string | undefined;
};
declare const _default: import("vitest/config").ViteUserConfigFnObject;
export default _default;
