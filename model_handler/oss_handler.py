import json
import os

import shortuuid
from eval_checker.eval_checker_constant import FILENAME_INDEX_MAPPING
from model_handler.handler import BaseHandler
from model_handler.model_style import ModelStyle
from model_handler.utils import (
    ast_parse,
    augment_prompt_by_languge,
    language_specific_pre_processing,
)


class OSSHandler(BaseHandler):
    def __init__(self, model_name, temperature=0.7, top_p=1, max_tokens=1000) -> None:
        super().__init__(model_name, temperature, top_p, max_tokens)
        self.model_style = ModelStyle.OSSMODEL

    def _format_prompt(prompt, function, test_category):
        SYSTEM_PROMPT = """
            You are an helpful assistant who has access to the following functions to help the user, you can use the functions if needed-
        """
        functions = ""
        if isinstance(function, list):
            for idx, func in enumerate(function):
                functions += "\n" + str(func)
        else:
            functions += "\n" + str(function)
        return f"SYSTEM: {SYSTEM_PROMPT}\n{functions}\nUSER: {prompt}\nASSISTANT: "

    @staticmethod
    def _batch_generate(
        test_question,
        model_path,
        temperature,
        max_tokens,
        top_p,
        stop_token_ids=None,
        max_model_len=None,
        num_gpus=1,
    ):
        from vllm import LLM, SamplingParams

        print("start generating, test question length: ", len(test_question))

        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stop_token_ids=stop_token_ids,
        )
        llm = LLM(
            model=model_path,
            dtype="float16",
            trust_remote_code=True,
            disable_custom_all_reduce=True,
            max_model_len=max_model_len,
            tensor_parallel_size=num_gpus,
        )
        outputs = llm.generate(test_question, sampling_params)

        final_ans_jsons = []
        for output in outputs:
            text = output.outputs[0].text
            final_ans_jsons.append(text)
        return final_ans_jsons

    @staticmethod
    def process_input(test_question, test_category, format_prompt_func):
        prompts = []
        for ques_json in test_question:
            prompt = augment_prompt_by_languge(ques_json["question"], test_category)
            functions = language_specific_pre_processing(
                ques_json["function"], test_category
            )
            prompts.append(format_prompt_func(prompt, functions, test_category))

        return prompts

    def inference(
        self,
        test_question,
        test_category,
        num_gpus,
        format_prompt_func=_format_prompt,
        stop_token_ids=None,
        max_model_len=None,
    ):
        test_question = self.process_input(
            test_question, test_category, format_prompt_func
        )

        ans_jsons = self._batch_generate(
            test_question=test_question,
            model_path=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            stop_token_ids=stop_token_ids,
            max_model_len=max_model_len,
            num_gpus=num_gpus,
        )

        return ans_jsons, {"input_tokens": 0, "output_tokens": 0, "latency": 0}

    def decode_ast(self, result, language="Python"):
        func = result
        if " " == func[0]:
            func = func[1:]
        if not func.startswith("["):
            func = "[" + func
        if not func.endswith("]"):
            func = func + "]"
        decode_output = ast_parse(func, language)
        return decode_output

    def decode_execute(self, result):
        return result

    def write(self, result, file_to_open):
        if not os.path.exists("./result"):
            os.mkdir("./result")
        if not os.path.exists("./result/" + self.model_name.replace("/", "_")):
            os.mkdir("./result/" + self.model_name.replace("/", "_"))
        with open(
            "./result/" + self.model_name.replace("/", "_") + "/" + file_to_open, "a+"
        ) as f:
            f.write(json.dumps(result) + "\n")

    def load_result(self, test_category):
        eval_data = []
        with open("./eval_data_total.json") as f:
            for line in f:
                eval_data.append(json.loads(line))
        result_list = []
        idx = 0
        with open(f"./result/{self.model_name}/result.json") as f:
            for line in f:
                if eval_data[idx]["test_category"] == test_category:
                    result_list.append(json.loads(line))
                idx += 1
        return result_list
