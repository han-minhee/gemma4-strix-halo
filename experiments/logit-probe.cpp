// Independent teacher-forced likelihood check using the public llama API.
#include "llama.h"
#include "ggml-backend.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

static std::string piece(const llama_vocab * vocab, llama_token token) {
    char out[1024];
    int n = llama_token_to_piece(vocab, token, out, sizeof(out), 0, true);
    return n > 0 ? std::string(out, n) : "?";
}

int main(int argc, char ** argv) {
    if (argc != 3) return 2;
    ggml_backend_load_all();
    llama_backend_init();
    auto mp = llama_model_default_params();
    mp.n_gpu_layers = 999;
    auto * model = llama_model_load_from_file(argv[1], mp);
    if (!model) return 3;
    const auto * vocab = llama_model_get_vocab(model);
    std::ifstream file(argv[2]);
    std::string text((std::istreambuf_iterator<char>(file)), {});
    std::vector<llama_token> tokens(text.size() + 16);
    int n = llama_tokenize(vocab, text.data(), text.size(), tokens.data(), tokens.size(), true, false);
    if (n < 512) return 4;
    auto cp = llama_context_default_params();
    cp.n_ctx = 512; cp.n_batch = 512; cp.n_ubatch = 512;
    cp.n_threads = 2; cp.n_threads_batch = 2;
    cp.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_ENABLED;
    auto * ctx = llama_init_from_model(model, cp);
    if (!ctx) return 5;
    auto batch = llama_batch_init(512, 0, 1);
    batch.n_tokens = 512;
    for (int i = 0; i < 512; ++i) {
        batch.token[i] = tokens[i]; batch.pos[i] = i;
        batch.n_seq_id[i] = 1; batch.seq_id[i][0] = 0; batch.logits[i] = true;
    }
    if (llama_decode(ctx, batch) != 0) return 6;
    double nll = 0;
    int nv = llama_vocab_n_tokens(vocab);
    for (int i = 256; i < 511; ++i) {
        const float * logits = llama_get_logits_ith(ctx, i);
        if (!logits) return 7;
        int top = std::max_element(logits, logits + nv) - logits;
        double sum = 0;
        for (int j = 0; j < nv; ++j) sum += std::exp(double(logits[j]) - logits[top]);
        double loss = logits[top] + std::log(sum) - logits[tokens[i + 1]];
        nll += loss;
        if (i < 266) std::printf("position=%d expected=[%s] top=[%s] nll=%.6f\n", i,
            piece(vocab, tokens[i + 1]).c_str(), piece(vocab, top).c_str(), loss);
    }
    std::printf("Independent PPL = %.6f; scored tokens = 255\n", std::exp(nll / 255));
    llama_batch_free(batch); llama_free(ctx); llama_model_free(model); llama_backend_free();
}
